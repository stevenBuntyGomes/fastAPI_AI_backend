# app/routes/bump.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
import re

from app.db.mongo import users_collection, bumps_collection
from app.services.socket_manager import emit_to_user
from app.utils.auth_utils import get_current_user  # your existing auth dependency

router = APIRouter(prefix="/bump", tags=["bump"])
HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class BumpBody(BaseModel):
    to_user_id: str = Field(..., description="Target user ObjectId as string")
    message: Optional[str] = "🔔 Bump!"
    token: Optional[str] = Field(None, description="Optional sender APNs token (will be saved if valid)")

@router.post("")
async def create_bump(body: BumpBody, current_user = Depends(get_current_user)):
    sender_id = str(current_user["_id"])
    to_user_id = body.to_user_id.strip()
    if not to_user_id:
        raise HTTPException(status_code=400, detail="Missing to_user_id")

    # If sender provides their own APNs token, store it
    if body.token and HEX_RE.match(body.token):
        await users_collection.update_one({"_id": ObjectId(sender_id)}, {"$set": {"apns_token": body.token}})

    # Persist bump
    bump_doc = {
        "from_user_id": sender_id,
        "to_user_id": to_user_id,
        "message": body.message or "🔔 Bump!",
        "created_at": datetime.utcnow(),
        "via": "rest",
    }
    await bumps_collection.insert_one(bump_doc)

    # Emit to target user over Socket.IO (if they’re online)
    delivered = await emit_to_user(
        to_user_id,
        "bump",
        {"type": "bump", "message": body.message or "🔔 Bump!", "from": sender_id}
    )

    return {"ok": True, "to": to_user_id, "delivered": delivered}
