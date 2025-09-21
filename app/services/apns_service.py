# app/services/apns_service.py
import os
import time
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
import jwt   # PyJWT
from bson import ObjectId

from app.db.mongo import devices_collection

# ---- Required env ----
APNS_KEY_ID        = os.getenv("APNS_KEY_ID")       # e.g. "F3S43P28PS"
APNS_TEAM_ID       = os.getenv("APNS_TEAM_ID")      # e.g. "9Z123ABC45"
APNS_BUNDLE_ID     = os.getenv("APNS_BUNDLE_ID")    # e.g. "com.yourco.yourapp"
APNS_AUTH_KEY_PATH = os.getenv("APNS_AUTH_KEY_PATH", "AuthKey_F3S43P28PS.p8")
APNS_ENV           = (os.getenv("APNS_ENV", "sandbox") or "sandbox").lower()

if not all([APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID]):
    raise RuntimeError("APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID must be set")

APNS_HOST = "https://api.push.apple.com" if APNS_ENV == "production" else "https://api.sandbox.push.apple.com"

# Cache the auth JWT for 50 minutes
_JWT_CACHE: Dict[str, Any] = {"token": None, "generated_at": 0}

def _load_private_key() -> bytes:
    with open(APNS_AUTH_KEY_PATH, "rb") as f:
        return f.read()

def _get_apns_jwt() -> str:
    now = int(time.time())
    if _JWT_CACHE["token"] and now - _JWT_CACHE["generated_at"] < 50 * 60:
        return _JWT_CACHE["token"]
    key = _load_private_key()
    # ES256 token; Apple wants "kid" in headers
    token = jwt.encode(
        {"iss": APNS_TEAM_ID, "iat": now},
        key,
        algorithm="ES256",
        headers={"kid": APNS_KEY_ID},
    )
    _JWT_CACHE.update(token=token, generated_at=now)
    return token

async def send_apns(
    token_hex: str,
    alert: Dict[str, str],
    custom: Optional[Dict[str, Any]] = None,
    badge: Optional[int] = None,
    sound: Optional[str] = "default",
    push_type: str = "alert",
) -> Dict[str, Any]:
    """
    Send one push to one device token.
    """
    url = f"{APNS_HOST}/3/device/{token_hex}"
    payload: Dict[str, Any] = {"aps": {}}

    if push_type == "alert":
        payload["aps"]["alert"] = alert
        if sound:
            payload["aps"]["sound"] = sound
        if badge is not None:
            payload["aps"]["badge"] = badge

    if custom:
        payload.update(custom)

    headers = {
        "authorization": f"bearer {_get_apns_jwt()}",
        "apns-topic": APNS_BUNDLE_ID,
        "apns-push-type": push_type,
        "apns-priority": "10" if push_type == "alert" else "5",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(http2=True, timeout=10) as client:
        resp = await client.post(url, headers=headers, json=payload)
    ok = resp.status_code == 200
    body: Dict[str, Any] = {}
    try:
        body = resp.json()
    except Exception:
        body = {"text": resp.text or ""}

    return {
        "ok": ok,
        "status": resp.status_code,
        "apns_id": resp.headers.get("apns-id"),
        "body": body,
    }

async def send_to_user(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send the same push to all iOS devices for a user.
    """
    tokens: List[str] = []
    async for d in devices_collection.find({"user_id": ObjectId(user_id), "platform": "ios"}):
        tokens.append(d["token"])

    results: List[Dict[str, Any]] = []
    for tk in tokens:
        res = await send_apns(
            tk,
            alert={"title": title, "body": body},
            custom={"data": data or {}},
            push_type="alert",
        )
        results.append(res)

    return {"sent": len(results), "results": results}
