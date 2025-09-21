# app/routes/devices.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import os, re
from bson import ObjectId

from app.db.mongo import devices_collection
from app.utils.auth_utils import get_current_user  # existing dependency

router = APIRouter(prefix="/devices", tags=["devices"])

# Accept hex tokens (Apple returns 32 bytes -> 64 hex chars; but allow longer for safety)
HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class RegisterTokenBody(BaseModel):
    token: str = Field(..., description="APNs device token as a hex string")
    bundle_id: Optional[str] = None
    environment: Optional[str] = Field(
        default=None, description='Optional override: "sandbox" or "production"'
    )

@router.post("/apns")
async def register_apns_token(
    body: RegisterTokenBody,
    current_user = Depends(get_current_user),
):
    # Normalize token: keep only hex chars
    raw = body.token or ""
    token = re.sub(r"[^0-9a-fA-F]", "", raw)
    if not HEX_RE.match(token):
        raise HTTPException(status_code=400, detail="Invalid APNs token format")

    try:
        user_oid = current_user["_id"]
        if not isinstance(user_oid, ObjectId):
            user_oid = ObjectId(str(user_oid))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid authenticated user")

    doc = {
        "user_id": user_oid,
        "platform": "ios",
        "token": token,
        "bundle_id": body.bundle_id or os.getenv("APNS_BUNDLE_ID"),
        "environment": (body.environment or os.getenv("APNS_ENV", "sandbox")).lower(),
        "updated_at": datetime.utcnow(),
    }

    # One row per (user_id, platform, token)
    await devices_collection.update_one(
        {"user_id": user_oid, "platform": "ios", "token": token},
        {"$set": doc},
        upsert=True,
    )

    return {"ok": True}
