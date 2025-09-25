# app/routes/devices.py
from fastapi import APIRouter, HTTPException, Request
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
    bundle_id: Optional[str] = Field(None, description="App bundle id (topic). Optional to store.")
    environment: Optional[Literal["sandbox", "production"]] = Field(
        None, description="If omitted, server infers (localhost => sandbox, else production)"
    )

def _infer_env_from_request(req: Request) -> str:
    # Best-effort inference: localhost means you're likely on a debug/sandbox build.
    host = (req.headers.get("host") or "").lower()
    if "localhost" in host or host.startswith("127.0.0.1") or host.startswith("10.") or host.startswith("192.168."):
        return "sandbox"
    return "production"

@router.post("/apns")
async def register_apns_device(body: RegisterDeviceBody, request: Request):
    # --- validate inputs ---
    try:
        user_oid = ObjectId(body.user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # Keep the sanitizer: prevents storing junk like "<abcd 1234>" or base64
    token = re.sub(r"[^0-9a-fA-F]", "", body.token or "")
    if not HEX_RE.fullmatch(token):
        raise HTTPException(status_code=400, detail="Invalid APNs token format")

    # Decide environment: prefer client hint, else infer from request host
    if body.environment:
        env_norm = body.environment.strip().lower()
        if env_norm not in ("production", "sandbox"):
            raise HTTPException(status_code=422, detail="environment must be 'sandbox' or 'production'")
    else:
        env_norm = _infer_env_from_request(request)

    # Store with capitalized label for readability (and to avoid mixing older lowercase values)
    env_label = "Production" if env_norm == "production" else "Sandbox"

    doc = {
        "user_id": user_oid,
        "platform": "ios",
        "token": token,
        "bundle_id": body.bundle_id or os.getenv("APNS_BUNDLE_ID"),  # ok if None at store time
        "environment": env_label,
        "updated_at": datetime.utcnow(),
    }

    # Upsert by (user_id, platform, environment) so sandbox & prod can both exist
    result = await devices_collection.update_one(
        {"user_id": user_oid, "platform": "ios", "environment": env_label},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )

    return {
        "ok": True,
        "environment": env_label,
        "matched": result.matched_count,
        "upserted_id": str(result.upserted_id) if result.upserted_id else None,
    }
