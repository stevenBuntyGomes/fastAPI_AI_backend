# app/routes/devices.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import os, re, sys, traceback                      # ← add sys, traceback
from bson import ObjectId
from pymongo.errors import DuplicateKeyError       # ← add DuplicateKeyError

from app.db.mongo import devices_collection
from app.utils.auth_utils import get_current_user

router = APIRouter(prefix="/devices", tags=["devices"])
HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class RegisterTokenBody(BaseModel):
    token: str = Field(..., description="APNs device token as a hex string")
    bundle_id: Optional[str] = None
    environment: Optional[Literal["sandbox", "production"]] = None

@router.post("/apns")
async def register_apns_token(
    body: RegisterTokenBody,
    current_user = Depends(get_current_user),
):
    # normalize + validate
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
        "user_id": user_oid,
        "platform": "ios",
        "token": token,
        "bundle_id": body.bundle_id or os.getenv("APNS_BUNDLE_ID"),
        "environment": env,
        "updated_at": datetime.utcnow(),
    }

    # ---- wrap your DB write in try/except (this is the bit you asked about) ----
    try:
        # keep your current uniqueness semantics:
        await devices_collection.update_one(
            {"user_id": user_oid, "platform": "ios", "token": token},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
        return {"ok": True}
    except DuplicateKeyError:
        # harmless duplicate – treat as success
        return {"ok": True, "note": "duplicate token index"}
    except Exception as e:
        # this line logs the real error to journald so we can see it
        print("❌ devices/apns DB error:", repr(e), file=sys.stderr)
        traceback.print_exc()
        # keep response generic
        raise HTTPException(status_code=500, detail="Database error while saving device")
