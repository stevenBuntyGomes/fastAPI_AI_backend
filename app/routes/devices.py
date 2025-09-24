# app/routes/devices.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId
import os, re

from app.db.mongo import devices_collection

router = APIRouter(prefix="/devices", tags=["devices"])

HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class RegisterDeviceBody(BaseModel):
    user_id: str = Field(..., description="Mongo ObjectId of the user")
    token: str = Field(..., description="APNs device token (hex)")
    bundle_id: Optional[str] = None
    environment: Optional[Literal["sandbox", "production"]] = None

@router.post("/apns")
async def register_apns_device(body: RegisterDeviceBody):
    # validate inputs
    try:
        user_oid = ObjectId(body.user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    token = re.sub(r"[^0-9a-fA-F]", "", body.token or "")
    if not HEX_RE.fullmatch(token):
        raise HTTPException(status_code=400, detail="Invalid APNs token format")

    env = (body.environment or os.getenv("APNS_ENV", "sandbox")).lower()
    if env not in ("sandbox", "production"):
        raise HTTPException(status_code=400, detail="environment must be 'sandbox' or 'production'")

    doc = {
        "user_id": user_oid,
        "platform": "ios",
        "token": token,
        "bundle_id": body.bundle_id or os.getenv("APNS_BUNDLE_ID"),
        "environment": env,
        "updated_at": datetime.utcnow(),
    }

    # One iOS token per user: upsert by (user_id, platform)
    await devices_collection.update_one(
        {"user_id": user_oid, "platform": "ios"},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )

    return {"ok": True}
