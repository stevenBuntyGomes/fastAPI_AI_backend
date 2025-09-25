# app/routes/devices.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId
import os, re, time, json
import jwt
import httpx

from app.db.mongo import devices_collection

router = APIRouter(prefix="/devices", tags=["devices"])

HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class RegisterDeviceBody(BaseModel):
    user_id: str = Field(..., description="Mongo ObjectId of the user")
    token: str = Field(..., description="APNs device token (hex)")
    bundle_id: Optional[str] = None
    environment: Optional[Literal["sandbox", "production"]] = Field(
        None, description="If omitted, server will auto-detect"
    )

# ---- APNs helpers ----
def _apns_jwt() -> str:
    key_path = os.getenv("APNS_KEY_PATH")
    team_id  = os.getenv("APNS_TEAM_ID")
    key_id   = os.getenv("APNS_KEY_ID")
    if not all([key_path, team_id, key_id]):
        raise RuntimeError("APNS credentials missing: APNS_KEY_PATH/TEAM_ID/KEY_ID")
    with open(key_path, "rb") as f:
        key = f.read()
    return jwt.encode({"iss": team_id, "iat": int(time.time())}, key,
                      algorithm="ES256", headers={"kid": key_id})

async def _probe_apns_environment(token: str, topic: str) -> Optional[str]:
    """
    Try Production first, then Sandbox. Return 'production' or 'sandbox', or None if both fail.
    Sends a background 'content-available' 1 with apns-expiration: 0 (minimizes user-visible delivery).
    """
    jwt_token = _apns_jwt()
    payload = {"aps": {"content-available": 1}}
    headers = {
        "authorization": f"bearer {jwt_token}",
        "apns-topic": topic,
        "apns-push-type": "background",
        "apns-expiration": "0",
        "apns-priority": "5",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(http2=True, timeout=5.0) as client:
        # Production
        url_prod = f"https://api.push.apple.com/3/device/{token}"
        r = await client.post(url_prod, headers=headers, content=json.dumps(payload))
        if r.status_code in (200, 202):
            return "production"
        if r.status_code == 400:
            # BadDeviceToken on prod often means it's a sandbox token
            try:
                reason = r.json().get("reason")
            except Exception:
                reason = None
            if reason == "BadDeviceToken":
                # Try sandbox
                url_sbx = f"https://api.sandbox.push.apple.com/3/device/{token}"
                r2 = await client.post(url_sbx, headers=headers, content=json.dumps(payload))
                if r2.status_code in (200, 202):
                    return "sandbox"

        # If we got here, neither accepted cleanly
        return None

@router.post("/apns")
async def register_apns_device(body: RegisterDeviceBody):
    # --- validate inputs ---
    try:
        user_oid = ObjectId(body.user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # Keep the sanitizer: prevents storing junk like "<abcd 1234>" or base64
    token = re.sub(r"[^0-9a-fA-F]", "", body.token or "")
    if not HEX_RE.fullmatch(token):
        raise HTTPException(status_code=400, detail="Invalid APNs token format")

    bundle_id = body.bundle_id or os.getenv("APNS_BUNDLE_ID")
    if not bundle_id:
        raise HTTPException(status_code=400, detail="Missing bundle_id")

    # --- decide environment ---
    env_norm: Optional[str] = None
    if body.environment:
        env_norm = body.environment.strip().lower()  # 'production' or 'sandbox'
    else:
        # Auto-detect by probing APNs once
        try:
            env_norm = await _probe_apns_environment(token, bundle_id)
        except RuntimeError as e:
            # APNS creds not configured -> default to production (TestFlight/App Store are production)
            env_norm = "production"

    if env_norm not in ("production", "sandbox"):
        # If we truly can't tell, be explicit
        raise HTTPException(status_code=422, detail="Unable to determine APNs environment")

    # Store with capitalized label for clarity in DB/UI
    env_label = "Production" if env_norm == "production" else "Sandbox"

    doc = {
        "user_id": user_oid,
        "platform": "ios",
        "token": token,
        "bundle_id": bundle_id,
        "environment": env_label,   # "Production" or "Sandbox"
        "updated_at": datetime.utcnow(),
    }

    # --- Upsert by (user_id, platform, environment) so sandbox and prod can coexist ---
    result = await devices_collection.update_one(
        {"user_id": user_oid, "platform": "ios", "environment": env_label},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )

    return {
        "ok": True,
        "environment": env_label,
        "matched": result.matched_count,
        "upserted": bool(result.upserted_id),
    }
