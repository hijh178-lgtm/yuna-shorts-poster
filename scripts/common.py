"""공통: 인스타 API 호출, 파일 읽고 쓰기.
토큰은 GitHub Secrets(IG_TOKEN, IG_USER_ID)에서 환경변수로 받는다. 채널 정보는 저장소의 config.json (공개돼도 되는 것만)."""
import json, os, urllib.parse, urllib.request

G = "https://graph.instagram.com/v21.0"
TOK = os.environ.get("IG_TOKEN", "")
IGID = os.environ.get("IG_USER_ID", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "")
CONF = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
INPOCK = CONF["inpock_url"]
HEAD = CONF["disclosure"]
MY_USERNAME = CONF["instagram_username"]


def api(path, data=None):
    url = f"{G}/{path}"
    if data is None:
        url += ("&" if "?" in url else "?") + "access_token=" + TOK
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode({**data, "access_token": TOK}).encode())
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"IG API {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")


def load(name, default):
    p = os.path.join(ROOT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def save(name, obj):
    json.dump(obj, open(os.path.join(ROOT, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def raw_url(path):
    """저장소 파일의 공개 주소 (인스타가 영상을 가져가는 주소). 저장소가 공개(Public)여야 한다."""
    return f"https://raw.githubusercontent.com/{REPO}/main/{urllib.parse.quote(path)}"


# ---------- 쓰레드 (선택: Secrets 에 TH_TOKEN·TH_USER_ID 가 있을 때만) ----------
TG = "https://graph.threads.net/v1.0"
TH_TOK = os.environ.get("TH_TOKEN", "")
THID = os.environ.get("TH_USER_ID", "")


def th_api(path, data=None):
    url = f"{TG}/{path}"
    if data is None:
        url += ("&" if "?" in url else "?") + "access_token=" + TH_TOK
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode({**data, "access_token": TH_TOK}).encode())
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Threads API {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")
