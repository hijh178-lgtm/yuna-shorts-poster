"""인스타 토큰 자동 연장. 인스타 장기 토큰은 60일이면 끝나므로, 한 달에 두 번 새 토큰으로 바꿔 GitHub Secret(IG_TOKEN)에 다시 넣는다.

필요: Secret GH_PAT (이 저장소의 Secrets 를 고칠 수 있는 GitHub 토큰). 토큰 값은 로그에 찍지 않는다.
"""
import base64, json, os, urllib.request

from nacl import encoding, public

TOK = os.environ["IG_TOKEN"]
PAT = os.environ["GH_PAT"]
REPO = os.environ["GITHUB_REPOSITORY"]

r = json.load(urllib.request.urlopen(
    "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=" + TOK, timeout=60))
new = r["access_token"]
days = int(r.get("expires_in", 0)) // 86400

H = {"Authorization": "token " + PAT, "Accept": "application/vnd.github+json", "User-Agent": "token-refresh",
     "Content-Type": "application/json"}
key = json.load(urllib.request.urlopen(urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=H), timeout=30))
box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
enc = base64.b64encode(box.encrypt(new.encode())).decode()
urllib.request.urlopen(urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/actions/secrets/IG_TOKEN", method="PUT", headers=H,
    data=json.dumps({"encrypted_value": enc, "key_id": key["key_id"]}).encode()), timeout=30)
print(f"인스타 토큰 연장 완료 (앞으로 {days}일 유효)")

# 쓰레드 토큰도 같은 방식으로 연장 (TH_TOKEN 이 있을 때만)
TH = os.environ.get("TH_TOKEN", "")
if TH:
    r = json.load(urllib.request.urlopen(
        "https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token=" + TH, timeout=60))
    enc = base64.b64encode(box.encrypt(r["access_token"].encode())).decode()
    urllib.request.urlopen(urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/secrets/TH_TOKEN", method="PUT", headers=H,
        data=json.dumps({"encrypted_value": enc, "key_id": key["key_id"]}).encode()), timeout=30)
    print(f"쓰레드 토큰 연장 완료 (앞으로 {int(r.get('expires_in', 0)) // 86400}일 유효)")
