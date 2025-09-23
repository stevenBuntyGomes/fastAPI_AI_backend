# app/routes/bump.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

from app.db.mongo import users_collection, bumps_collection
from app.services.apns_service import send_to_user as send_apns_to_user
from app.utils.auth_utils import get_current_user  # existing auth dependency

router = APIRouter(prefix="/bump", tags=["bump"])

class BumpBody(BaseModel):
    to_user_id: str = Field(..., description="Recipient user ObjectId (string)")
    message: Optional[str] = Field(default="🔔 Bump!")

@router.post("")
async def create_bump(body: BumpBody, current_user = Depends(get_current_user)):
    # sender
    try:
        sender_oid = current_user["_id"]
        if not isinstance(sender_oid, ObjectId):
            sender_oid = ObjectId(str(sender_oid))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid authenticated user")

    # recipient
    try:
        to_oid = ObjectId(body.to_user_id.strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid to_user_id")

    # ensure recipient exists
    if not await users_collection.find_one({"_id": to_oid}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Recipient not found")

    # persist bump
    msg = body.message or "🔔 Bump!"
    now = datetime.utcnow()
    bump_doc = {
        "from_user_id": sender_oid,
        "to_user_id": to_oid,
        "message": msg,
        "created_at": now,
        "via": "rest",
    }
    ins = await bumps_collection.insert_one(bump_doc)
    bump_id = ins.inserted_id

    # APNs push only (no Socket.IO)
    try:
        apns_result = await send_apns_to_user(
            user_id=str(to_oid),
            title="New bump",
            body=msg,
            data={
                "type": "bump",
                "from": str(sender_oid),
                "to": str(to_oid),
                "bump_id": str(bump_id),
                "created_at": now.isoformat() + "Z",
            },
        )
    except Exception as e:
        apns_result = {"sent": 0, "results": [], "error": str(e)}

    return {
        "ok": True,
        "to": str(to_oid),
        "bump_id": str(bump_id),
        "apns": apns_result,
    }
