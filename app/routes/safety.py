# app/routes/safety.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

from ..db.mongo import reports_collection, blocks_collection, community_collection
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/safety", tags=["Safety"])

class ReportCreate(BaseModel):
    content_id: str               # post_id | comment_id
    content_type: str             # "post" | "comment"
    reason: str
    details: str | None = None

class BlockRequest(BaseModel):
    target_user_id: str

def _oid(s: str) -> ObjectId:
    if not ObjectId.is_valid(s):
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    return ObjectId(s)

async def _auto_hide(content_id: str, content_type: str):
    if content_type == "post":
        await community_collection.update_one({"_id": _oid(content_id)}, {"$set": {"status":"hidden","hidden_reason":"reported"}})
    elif content_type == "comment":
        await community_collection.update_one({"comments.id": content_id}, {"$set": {"comments.$.status":"hidden","comments.$.hidden_reason":"reported"}})

@router.post("/reports")
async def create_report(payload: ReportCreate, user=Depends(get_current_user)):
    await reports_collection.insert_one({
        "reporter_id": str(user["_id"]),
        "content_id": payload.content_id,
        "content_type": payload.content_type,
        "reason": payload.reason,
        "details": payload.details,
        "status": "open",
        "created_at": datetime.utcnow(),
    })
    await _auto_hide(payload.content_id, payload.content_type)  # act immediately
    return {"ok": True}

@router.post("/block")
async def block_user(payload: BlockRequest, user=Depends(get_current_user)):
    await blocks_collection.update_one(
        {"user_id": str(user["_id"])},
        {"$addToSet": {"blocked": payload.target_user_id}},
        upsert=True
    )
    return {"ok": True}

@router.post("/unblock")
async def unblock_user(payload: BlockRequest, user=Depends(get_current_user)):
    await blocks_collection.update_one(
        {"user_id": str(user["_id"])},
        {"$pull": {"blocked": payload.target_user_id}}
    )
    return {"ok": True}
