# app/services/apns_service.py
import os, time, json, jwt, httpx
from functools import lru_cache
from typing import Optional, Dict

APNS_KEY_ID       = os.getenv("APNS_KEY_ID")              # e.g., 2UUSKYV967
APNS_TEAM_ID      = os.getenv("APNS_TEAM_ID")             # e.g., SUVY329496
APNS_BUNDLE_ID    = os.getenv("APNS_BUNDLE_ID")           # e.g., com.breathr.breathrapp
APNS_TIMEOUT      = float(os.getenv("APNS_TIMEOUT", "8"))
APNS_ENV_DEFAULT  = os.getenv("APNS_ENV", "production").strip().lower()
APNS_USE_SANDBOX  = os.getenv("APNS_USE_SANDBOX", "false").strip().lower() in ("1","true","yes","on")

def _host(env: str) -> str:
    return "https://api.push.apple.com" if env == "production" else "https://api.sandbox.push.apple.com"

def _current_env(explicit: Optional[str] = None) -> str:
    if explicit in ("production", "sandbox"):
        return explicit
    # honor APNS_USE_SANDBOX first, then APNS_ENV
    return "sandbox" if APNS_USE_SANDBOX or APNS_ENV_DEFAULT == "sandbox" else "production"

@lru_cache(maxsize=1)
def _get_private_key() -> bytes:
    """Return PEM bytes from inline env or file path; raise clear errors if misconfigured."""
    pem_inline = os.getenv("APNS_P8") or os.getenv("APNS_AUTH_KEY_PEM")
    if pem_inline and pem_inline.strip().startswith("-----BEGIN"):
        return pem_inline.encode()

    path = os.getenv("APNS_P8_FILE") or os.getenv("APNS_AUTH_KEY_PATH")
    if not path:
        raise RuntimeError("APNS key not configured (APNS_P8/APNS_AUTH_KEY_PEM/APNS_P8_FILE/APNS_AUTH_KEY_PATH)")
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(b"-----BEGIN"):
        raise ValueError("APNS key file is not PEM")
    return data

def _jwt_token() -> str:
    if not APNS_KEY_ID or not APNS_TEAM_ID:
        raise RuntimeError("APNS_KEY_ID or APNS_TEAM_ID is missing")
    payload = {"iss": APNS_TEAM_ID, "iat": int(time.time())}
    headers = {"alg": "ES256", "kid": APNS_KEY_ID}
    return jwt.encode(payload, _get_private_key(), algorithm="ES256", headers=headers)

async def send_apns_push(
    token_hex: str,
    alert: Dict,
    env: str = None,                 # "production" | "sandbox" | None
    push_type: str = "alert",
    thread_id: Optional[str] = None,
    category: Optional[str] = None,
    badge: Optional[int] = None,
) -> Dict:
    """
    Returns: {"ok": bool, "status": int, "reason": str|None, "apns_id": str|None, "body": dict|{text}}
    """
    use_env = _current_env(env)
    url = f"{_host(use_env)}/3/device/{token_hex}"
    jwt_token = _jwt_token()

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

    try:
        async with httpx.AsyncClient(http2=True, timeout=APNS_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except Exception as e:
        return {"ok": False, "status": 0, "reason": "Exception", "apns_id": None, "body": {"error": str(e)}}

    apns_id = resp.headers.get("apns-id")
    try:
        body = resp.json()
    except Exception:
        body = {"text": resp.text}

    reason = body.get("reason") if isinstance(body, dict) else None
    return {"ok": 200 <= resp.status_code < 300, "status": resp.status_code, "reason": reason, "apns_id": apns_id, "body": body}
