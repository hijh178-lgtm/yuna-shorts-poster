"""댓글 → 자동 DM: posted.json 의 릴스마다 댓글을 읽어 키워드가 있으면 버튼 카드(비공개 답장)를 1번 보낸다.
보낸 기록은 dm_sent.json (댓글 id 기준). 카드 = 제목 "NNN. 제품 정보예요 :)" / 설명 대가성 문구 + "NNN번 검색" / 버튼 인포크.
"""
import json, time
from common import api, load, save, IGID, INPOCK, HEAD, MY_USERNAME, CONF

COMMON = CONF.get("dm_common_keywords", ["나도", "정보", "링크", "댓글"])


def comments(mid):
    out, url = [], f"{mid}/comments?fields=id,text,username,timestamp&limit=50"
    r = api(url)
    out += r.get("data", [])
    nxt = r.get("paging", {}).get("cursors", {}).get("after")
    while nxt and len(out) < 500:
        r = api(url + "&after=" + nxt)
        out += r.get("data", [])
        nxt = r.get("paging", {}).get("cursors", {}).get("after") if r.get("data") else None
    return out


def card(comment_id, label, title):
    """label = 검색 번호 글자 ("003" 또는 랭킹형 "003~005")."""
    msg = {"attachment": {"type": "template", "payload": {"template_type": "generic", "elements": [
        {"title": f"{label}. {title} 정보예요 :)", "subtitle": f"{HEAD}\n아래 버튼 누르고 {label}번을 검색하세요",
         "buttons": [{"type": "web_url", "url": INPOCK, "title": "제품 정보 보기"}]}]}}}
    return api(f"{IGID}/messages", {"recipient": json.dumps({"comment_id": comment_id}), "message": json.dumps(msg)})


posted, sent = load("posted.json", []), load("dm_sent.json", {})
n = 0
for p in posted:
    words = [w.lower() for w in (p.get("dm_keywords") or []) + COMMON]
    for c in comments(p["media_id"]):
        if c["id"] in sent or c.get("username") == MY_USERNAME:
            continue
        if not any(w in (c.get("text") or "").lower() for w in words):
            continue
        try:
            r = card(c["id"], p.get("no_label") or f"{p['no']:03d}", p["block_title"])
            sent[c["id"]] = {"no": p["no"], "text": c.get("text"), "at": time.strftime("%Y-%m-%d %H:%M"), "message_id": r.get("message_id")}
            n += 1
            print("DM:", p["no"], c.get("text"))
        except RuntimeError as e:
            sent[c["id"]] = {"no": p["no"], "text": c.get("text"), "error": str(e)[:200]}
            print("실패:", c["id"], e)
save("dm_sent.json", sent)
print(f"게시물 {len(posted)}개 확인, DM {n}건")
