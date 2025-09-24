# app/routes/devices.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import os, re, sys, traceback
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db.mongo import devices_collection
from app.utils.auth_utils import get_current_user

router = APIRouter(prefix="/devices", tags=["devices"])

# Apple token: 32 bytes => 64 hex chars; allow longer to be tolerant
HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class RegisterTokenBody(BaseModel):
    token: str = Field(..., description="APNs device token (hex)")
    bundle_id: Optional[str] = None
    environment: Optional[Literal["sandbox", "production"]] = None

@router.post("/apns")
async def register_apns_token(
    body: RegisterTokenBody,
    current_user = Depends(get_current_user),
):
    # normalize + validate token
    raw = body.token or ""
    token = re.sub(r"[^0-9a-fA-F]", "", raw)
    if not HEX_RE.match(token):
        raise HTTPException(status_code=400, detail="Invalid APNs token format")

    # auth → ObjectId
    try:
        user_oid = current_user["_id"]
        if not isinstance(user_oid, ObjectId):
            user_oid = ObjectId(str(user_oid))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid/expired authentication")

    env = (body.environment or os.getenv("APNS_ENV", "sandbox")).lower()
    if env not in ("sandbox", "production"):
        raise HTTPException(status_code=400, detail="environment must be 'sandbox' or 'production'")

    doc = {
        "user_id": user_oid,                # ← reassign device to this user
        "platform": "ios",
        "token": token,
        "bundle_id": body.bundle_id or os.getenv("APNS_BUNDLE_ID"),
        "environment": env,
        "updated_at": datetime.utcnow(),
    }

    # Option A: upsert by (platform, token) so each physical device is unique
    try:
        await devices_collection.update_one(
            {"platform": "ios", "token": token},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
        return {"ok": True}
    except DuplicateKeyError:
        # rare race; retry as non-upsert
        await devices_collection.update_one(
            {"platform": "ios", "token": token},
            {"$set": doc},
            upsert=False,
        )
        return {"ok": True, "note": "resolved duplicate index"}
    except Exception as e:
        print("❌ devices/apns DB error:", repr(e), file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Database error while saving device")
