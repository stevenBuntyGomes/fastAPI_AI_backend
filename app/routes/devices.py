# app/routes/devices.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import re
from bson import ObjectId

from app.db.mongo import users_collection
from app.utils.auth_utils import get_current_user  # your existing dependency

router = APIRouter(prefix="/devices", tags=["devices"])
HEX_RE = re.compile(r"^[0-9a-fA-F]{64,256}$")

class RegisterTokenBody(BaseModel):
    token: str = Field(..., description="APNs device token")

@router.post("/apns")
async def register_apns_token(
    body: RegisterTokenBody,
    current_user=Depends(get_current_user)
):
    token = body.token.strip()
    if not HEX_RE.match(token):
        raise HTTPException(status_code=400, detail="Invalid APNs token format")

    await users_collection.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"apns_token": token}}
    )
    return {"ok": True}
