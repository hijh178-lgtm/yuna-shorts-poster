"""예약 게시: posts.json 에서 시간(한국시간)이 지난 것 하나를 인스타 릴스로 올린다.

posts.json 항목: {"no": 7, "file": "videos/007.mp4", "caption": "...", "block_title": "...", "dm_keywords": [...],
                   "at": "2026-10-07 19:00", "done": null, "media_id": null, "permalink": null}
올린 뒤 posted.json(댓글 DM 감시 목록)에도 넣는다. 실패하면 error 를 적고 done 처리(같은 걸 계속 재시도하지 않음).
쓰레드 토큰(TH_TOKEN)이 있으면 같은 영상을 쓰레드에도 올리고, 첫 답글에 상품 번호·인포크 링크·대가성 문구를 단다.
쓰레드는 인스타와 따로 기록(th_done·th_error)해서, 쓰레드가 실패해도 인스타 게시에는 영향이 없다.
"""
import datetime as dt, os, time, traceback
from common import api, load, save, raw_url, IGID, th_api, TH_TOK, THID, INPOCK, HEAD

KST = dt.timezone(dt.timedelta(hours=9))


def threads_text(p):
    """인스타 캡션 → 쓰레드 본문. 쓰레드엔 댓글 자동 DM 이 없으니 DM 줄을 빼고 '첫 댓글에 링크' 로 바꾼다. 500자 제한."""
    lines = []
    for l in p["caption"].splitlines():
        if "DM" in l:
            continue
        if "프로필 링크" in l:
            l = "👇 상품 링크는 첫 댓글에 있어요"
        lines.append(l)
    t = "\n".join(lines).strip()
    while "\n\n\n" in t:
        t = t.replace("\n\n\n", "\n\n")
    if not t.startswith("[광고]"):
        t = "[광고] " + t
    return t[:500]


def post_threads(p, now):
    c = th_api(f"{THID}/threads", {"media_type": "VIDEO", "video_url": raw_url(p["file"]), "text": threads_text(p)})
    cid = c["id"]
    for _ in range(60):
        st = th_api(f"{cid}?fields=status,error_message")
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError("쓰레드 처리 실패: " + str(st))
        time.sleep(5)
    else:
        raise RuntimeError("쓰레드 인코딩 대기 시간 초과")
    tid = th_api(f"{THID}/threads_publish", {"creation_id": cid})["id"]
    info = th_api(f"{tid}?fields=permalink")
    label = p.get("no_label") or f"{int(p['no']):03d}"
    reply = f"{label}번 {p.get('block_title', '')} 👉 {INPOCK}\n(인포크 페이지에서 {label}번을 찾으세요)\n\n{HEAD}"
    r = th_api(f"{THID}/threads", {"media_type": "TEXT", "text": reply[:500], "reply_to_id": tid})
    time.sleep(3)
    th_api(f"{THID}/threads_publish", {"creation_id": r["id"]})
    p.update(th_done=now, th_id=tid, th_permalink=info.get("permalink"))
    print(now, "쓰레드 게시:", p["no"], info.get("permalink"))


now =dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
posts = load("posts.json", [])
for p in posts:
    if p.get("done") or not p.get("at") or p["at"] > now:
        continue
    try:
        if not os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p["file"])):
            raise RuntimeError("영상 파일이 저장소에 없음: " + p["file"])
        c = api(f"{IGID}/media", {"media_type": "REELS", "video_url": raw_url(p["file"]), "caption": p["caption"], "share_to_feed": "true"})
        cid = c["id"]
        for _ in range(60):
            st = api(f"{cid}?fields=status_code,status")
            if st.get("status_code") == "FINISHED":
                break
            if st.get("status_code") == "ERROR":
                raise RuntimeError("인스타 처리 실패: " + str(st))
            time.sleep(5)
        else:
            raise RuntimeError("인코딩 대기 시간 초과")
        mid = api(f"{IGID}/media_publish", {"creation_id": cid})["id"]
        info = api(f"{mid}?fields=permalink")
        p.update(done=now, media_id=mid, permalink=info.get("permalink"))
        posted = load("posted.json", [])
        posted.append({"no": p["no"], "media_id": mid, "permalink": info.get("permalink"),
                       "no_label": p.get("no_label"), "block_title": p["block_title"],
                       "dm_keywords": p.get("dm_keywords", [])})
        save("posted.json", posted)
        print(now, "게시:", p["no"], info.get("permalink"))
        if TH_TOK and THID and not p.get("th_done"):
            try:
                post_threads(p, now)
            except Exception as e:
                p.update(th_done=now, th_error=str(e)[:300])
                print(now, "쓰레드 실패:", p["no"], e)
    except Exception as e:
        p.update(done=now, error=str(e)[:300])
        print(now, "실패:", p["no"], e)
        traceback.print_exc()
    save("posts.json", posts)
    break
else:
    print(now, "올릴 예약 없음")
