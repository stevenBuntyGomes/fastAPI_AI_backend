# app/routes/moderation_admin.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timedelta
from bson import ObjectId

from ..db.mongo import reports_collection, community_collection, users_collection
from ..utils.auth_utils import get_current_admin_user

router = APIRouter(prefix="/admin/moderation", tags=["Admin"])

class ResolvePayload(BaseModel):
    action: str                     # remove_content | restore_content | suspend_user | ban_user | ignore
    offender_user_id: str | None = None
    notes: str | None = None
    suspend_hours: int | None = 24

def _oid(s: str) -> ObjectId:
    if not ObjectId.is_valid(s): raise HTTPException(status_code=400, detail="Invalid ObjectId")
    return ObjectId(s)

@router.get("/reports")
async def list_reports(status: str = Query("open"), admin=Depends(get_current_admin_user)):
    cur = reports_collection.find({"status": status}).sort("created_at", -1)
    return [{**r, "_id": str(r["_id"])} async for r in cur]

@router.post("/reports/{report_id}/resolve")
async def resolve_report(report_id: str, payload: ResolvePayload, admin=Depends(get_current_admin_user)):
    rep = await reports_collection.find_one({"_id": _oid(report_id)})
    if not rep: raise HTTPException(status_code=404, detail="Report not found")

    if payload.action == "remove_content":
        if rep["content_type"] == "post":
            await community_collection.delete_one({"_id": _oid(rep["content_id"])})
        elif rep["content_type"] == "comment":
            await community_collection.update_one({"comments.id": rep["content_id"]}, {"$pull": {"comments": {"id": rep["content_id"]}}})
    elif payload.action == "restore_content":
        if rep["content_type"] == "post":
            await community_collection.update_one({"_id": _oid(rep["content_id"])}, {"$set": {"status":"visible"}, "$unset": {"hidden_reason":""}})
        elif rep["content_type"] == "comment":
            await community_collection.update_one({"comments.id": rep["content_id"]}, {"$set": {"comments.$.status":"visible"}, "$unset": {"comments.$.hidden_reason":""}})
    elif payload.action == "suspend_user":
        if not payload.offender_user_id: raise HTTPException(status_code=400, detail="offender_user_id required")
        until = datetime.utcnow() + timedelta(hours=payload.suspend_hours or 24)
        await users_collection.update_one({"_id": _oid(payload.offender_user_id)}, {"$set": {"is_suspended": True, "suspended_until": until}})
    elif payload.action == "ban_user":
        if not payload.offender_user_id: raise HTTPException(status_code=400, detail="offender_user_id required")
        await users_collection.update_one({"_id": _oid(payload.offender_user_id)}, {"$set": {"is_banned": True}})
    elif payload.action == "ignore":
        pass
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    await reports_collection.update_one({"_id": rep["_id"]}, {"$set": {"status":"resolved", "resolved_at": datetime.utcnow(), "resolver_id": str(admin['_id']), "notes": payload.notes}})
    return {"ok": True}
