"""Send one private reply for each eligible Instagram comment.

The matching, duplicate handling, and send-failure state behavior intentionally
match the existing workflow. The counters below make each exclusion visible in
GitHub Actions without printing comment text.
"""
import json
import time

from common import api, load, save, IGID, INPOCK, HEAD, MY_USERNAME, CONF

COMMON = CONF.get("dm_common_keywords", ["나도", "정보", "링크", "댓글"])


def comments(mid, api_fn=None, stats=None):
    """Fetch comments using the same pagination and 500-comment cap as before."""
    api_fn = api_fn or api
    out, url = [], f"{mid}/comments?fields=id,text,username,timestamp&limit=50"
    response = api_fn(url)
    if stats is not None:
        stats["comment_api_pages"] += 1
    out += response.get("data", [])
    nxt = response.get("paging", {}).get("cursors", {}).get("after")
    while nxt and len(out) < 500:
        response = api_fn(url + "&after=" + nxt)
        if stats is not None:
            stats["comment_api_pages"] += 1
        out += response.get("data", [])
        nxt = response.get("paging", {}).get("cursors", {}).get("after") if response.get("data") else None
    return out


def card(comment_id, label, title, api_fn=None):
    """Send the existing generic card as a private reply to the comment."""
    api_fn = api_fn or api
    msg = {"attachment": {"type": "template", "payload": {"template_type": "generic", "elements": [
        {"title": f"{label}. {title} 정보예요 :)", "subtitle": f"{HEAD}\n아래 버튼 누르고 {label}번을 검색하세요",
         "buttons": [{"type": "web_url", "url": INPOCK, "title": "제품 정보 보기"}]}]}}}
    return api_fn(f"{IGID}/messages", {"recipient": json.dumps({"comment_id": comment_id}), "message": json.dumps(msg)})


def run(api_fn=None, save_fn=None, printer=None):
    """Run one DM pass. api_fn is injectable so tests never contact Instagram."""
    api_fn = api_fn or api
    save_fn = save_fn or save
    printer = printer or print
    posted, sent = load("posted.json", []), load("dm_sent.json", {})
    stats = {
        "posts_checked": len(posted),
        "comments_fetched": 0,
        "comment_api_pages": 0,
        "keyword_matches": 0,
        "keyword_mismatches": 0,
        "duplicate_excluded": 0,
        "own_comments_excluded": 0,
        "send_succeeded": 0,
        "send_failed": 0,
    }

    for post in posted:
        words = [word.lower() for word in (post.get("dm_keywords") or []) + COMMON]
        fetched = comments(post["media_id"], api_fn=api_fn, stats=stats)
        stats["comments_fetched"] += len(fetched)
        for comment in fetched:
            if comment["id"] in sent:
                stats["duplicate_excluded"] += 1
                continue
            if comment.get("username") == MY_USERNAME:
                stats["own_comments_excluded"] += 1
                continue
            matched = any(word in (comment.get("text") or "").lower() for word in words)
            if not matched:
                stats["keyword_mismatches"] += 1
                continue

            stats["keyword_matches"] += 1
            try:
                result = card(
                    comment["id"],
                    post.get("no_label") or f"{post['no']:03d}",
                    post["block_title"],
                    api_fn=api_fn,
                )
                sent[comment["id"]] = {
                    "no": post["no"],
                    "text": comment.get("text"),
                    "at": time.strftime("%Y-%m-%d %H:%M"),
                    "message_id": result.get("message_id"),
                }
                stats["send_succeeded"] += 1
                printer(f"DM 성공: 게시물 {post['no']}, 댓글 {comment['id']}")
            except RuntimeError as error:
                # Preserve existing behavior: failed IDs are recorded, so a
                # later run excludes them instead of retrying automatically.
                sent[comment["id"]] = {
                    "no": post["no"],
                    "text": comment.get("text"),
                    "error": str(error)[:200],
                }
                stats["send_failed"] += 1
                printer(f"DM 실패: 게시물 {post['no']}, 댓글 {comment['id']}: {error}")

    save_fn("dm_sent.json", sent)
    printer(
        "DM 진단: "
        f"게시물 {stats['posts_checked']}개, 댓글 조회 {stats['comments_fetched']}건 "
        f"(API 페이지 {stats['comment_api_pages']}), "
        f"키워드 일치 {stats['keyword_matches']}건 / 불일치 {stats['keyword_mismatches']}건, "
        f"중복 제외 {stats['duplicate_excluded']}건, 본인 댓글 제외 {stats['own_comments_excluded']}건, "
        f"발송 성공 {stats['send_succeeded']}건 / 실패 {stats['send_failed']}건"
    )
    return stats


if __name__ == "__main__":
    run()
