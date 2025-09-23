# app/services/apns_service.py
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx
import jwt  # PyJWT
from bson import ObjectId

from app.db.mongo import devices_collection, users_collection

# ---- Required env ----
APNS_KEY_ID        = os.getenv("APNS_KEY_ID")        # e.g. "F3S43P28PS"
APNS_TEAM_ID       = os.getenv("APNS_TEAM_ID")       # e.g. "SUVY329496"
APNS_BUNDLE_ID     = os.getenv("APNS_BUNDLE_ID")     # e.g. "com.breathr.breathrapp"
APNS_AUTH_KEY_PATH = os.getenv("APNS_AUTH_KEY_PATH", "AuthKey_F3S43P28PS.p8")
APNS_ENV           = (os.getenv("APNS_ENV", "sandbox") or "sandbox").lower()

if not all([APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID]):
    raise RuntimeError("APNS_KEY_ID, APNS_TEAM_ID, and APNS_BUNDLE_ID must be set")

APNS_HOST = "https://api.push.apple.com" if APNS_ENV == "production" else "https://api.sandbox.push.apple.com"

# Cache the auth JWT for 50 minutes
_JWT_CACHE: Dict[str, Any] = {"token": None, "generated_at": 0}

# Accept hex tokens (Apple returns 32 bytes -> 64 hex chars; allow longer just in case)
HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

def _sanitize_token(token: str) -> Optional[str]:
    if not token:
        return None
    # keep only hex chars
    t = re.sub(r"[^0-9a-fA-F]", "", token)
    return t if HEX_RE.match(t) else None

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
    Returns a dict like: {"ok": bool, "status": int, "apns_id": str|None, "body": {...}}
    Never raises; catches and returns errors as {"ok": False, ...}.
    """
    try:
        token_clean = _sanitize_token(token_hex)
        if not token_clean:
            return {"ok": False, "status": 0, "apns_id": None, "body": {"error": "Invalid token format"}}

        url = f"{APNS_HOST}/3/device/{token_clean}"
        payload: Dict[str, Any] = {"aps": {}}

        if push_type == "alert":
            payload["aps"]["alert"] = alert or {}
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
        body: Dict[str, Any]
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
    except Exception as e:
        # Swallow errors to avoid crashing API routes
        return {"ok": False, "status": 0, "apns_id": None, "body": {"error": str(e)}}

async def _tokens_for_user(user_id: str) -> List[str]:
    """
    Collect all iOS tokens for a user. Prefers devices collection; falls back to users.apns_token (legacy).
    """
    tokens: List[str] = []
    try:
        uid = ObjectId(user_id)
    except Exception:
        return tokens

    # Preferred: devices collection
    try:
        async for d in devices_collection.find({"user_id": uid, "platform": "ios"}):
            tk = _sanitize_token((d or {}).get("token", ""))
            if tk:
                tokens.append(tk)
    except Exception:
        pass

    # Legacy fallback on users.apns_token
    if not tokens:
        try:
            u = await users_collection.find_one({"_id": uid}, {"apns_token": 1})
            tk = _sanitize_token((u or {}).get("apns_token", ""))
            if tk:
                tokens.append(tk)
        except Exception:
            pass

    return tokens

async def send_to_user(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send the same push to all iOS devices for a user.
    Returns {"sent": N, "results": [ send_apns(...) result dicts ]}.
    Never raises.
    """
    try:
        tokens = await _tokens_for_user(user_id)
        if not tokens:
            return {"sent": 0, "results": []}

        results: List[Dict[str, Any]] = []
        for tk in tokens:
            try:
                res = await send_apns(
                    tk,
                    alert={"title": title, "body": body},
                    custom={"data": data or {}},
                    push_type="alert",
                )
            except Exception as e:
                # belt-and-suspenders: shouldn't happen because send_apns already catches
                res = {"ok": False, "status": 0, "apns_id": None, "body": {"error": str(e)}}
            results.append(res)

        return {"sent": len(results), "results": results}
    except Exception as e:
        return {"sent": 0, "results": [], "error": str(e)}
