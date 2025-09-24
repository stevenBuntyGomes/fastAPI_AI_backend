# app/services/apns_client.py
import os, time, json, jwt, httpx
from typing import Optional, Dict

APNS_KEY_ID = os.getenv("APNS_KEY_ID")             # e.g., ABCDE12345
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID")           # e.g., 1A2BC3D4EF
APNS_BUNDLE_ID = os.getenv("APNS_BUNDLE_ID")       # e.g., com.breathr.breathrapp
APNS_AUTH_KEY_PEM = os.getenv("APNS_AUTH_KEY_PEM") # contents of AuthKey_<KEYID>.p8
APNS_TIMEOUT = float(os.getenv("APNS_TIMEOUT", "8"))

def _jwt_token() -> str:
    payload = {"iss": APNS_TEAM_ID, "iat": int(time.time())}
    headers = {"alg": "ES256", "kid": APNS_KEY_ID}
    return jwt.encode(payload, APNS_AUTH_KEY_PEM, algorithm="ES256", headers=headers)

def _host(env: str) -> str:
    return "https://api.push.apple.com" if env == "production" else "https://api.sandbox.push.apple.com"

async def send_apns_push(
    token_hex: str,
    alert: Dict,
    env: str = "production",
    push_type: str = "alert",
    thread_id: Optional[str] = None,
    category: Optional[str] = None,
    badge: Optional[int] = None,
) -> Dict:
    jwt_token = _jwt_token()
    url = f"{_host(env)}/3/device/{token_hex}"
    payload = {"aps": {"alert": alert, "sound": "default"}}
    if badge is not None:
        payload["aps"]["badge"] = badge
    if thread_id:
        payload["aps"]["thread-id"] = thread_id
    if category:
        payload["aps"]["category"] = category

    headers = {
        "authorization": f"bearer {jwt_token}",
        "apns-topic": APNS_BUNDLE_ID,
        "apns-push-type": push_type,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(http2=True, timeout=APNS_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, content=json.dumps(payload))
        body = {}
        try:
            body = resp.json()
        except Exception:
            body = {"text": resp.text}
        return {"ok": 200 <= resp.status_code < 300, "status": resp.status_code, "body": body}
