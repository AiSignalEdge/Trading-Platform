import urllib.request
import urllib.parse
import urllib.error
import json
import time

BASE = "http://127.0.0.1:8086"
ts = int(time.time())
email = f"hermes_{ts}@test.com"
password = "Test123456"
username = f"hermes_{ts}"

def api(method, path, token=None, body=None, form=False, api_key=None):
    url = BASE + path
    if body and form:
        data = urllib.parse.urlencode(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
    elif body:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
    else:
        req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if api_key:
        req.add_header("X-API-Key", api_key)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, r.read().decode()[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

# Register
status, body = api("POST", "/api/v1/auth/register",
    body={"username": username, "email": email, "password": password})
print(f"REGISTER: {status}\n{body[:200]}\n")

# Login
status, body = api("POST", "/api/v1/auth/login",
    body={"username": username, "password": password}, form=True)
print(f"LOGIN: {status}\n{body[:300]}\n")
token = ""
if status == 200:
    try:
        token = json.loads(body).get("access_token", "")
    except:
        pass
print(f"TOKEN: [{token}]\n")

tests = [
    ("/api/v1/dashboard/summary", None),
    ("/api/v1/dashboard/equity-curve?timeframe=1M", None),
    ("/api/v1/dashboard/equity-curve?timeframe=1M&aggregate=true", None),
    ("/api/v1/dashboard/live-summary", None),
    ("/api/v1/dashboard/active-strategies", None),
]

# API key from .env
API_KEY = "hermes-secret-api-key-2025"

for path, _ in tests:
    status, body = api("GET", path, token=token, api_key=API_KEY)
    label = "PASS" if status == 200 else "FAIL"
    print(f"[{label}] {status} {path}")
    if status != 200:
        print(f"  Body: {body[:200]}")
    else:
        try:
            data = json.loads(body)
            if "equity" in path:
                pts = data.get("points", [])
                print(f"  → {len(pts)} points, final_equity={data.get('final_equity')}, total_return={data.get('total_return_pct')}")
            else:
                print(f"  → equity={data.get('total_equity')}, mode={data.get('mode')}, open_pos={data.get('open_positions')}")
        except:
            print(f"  → {body[:100]}")