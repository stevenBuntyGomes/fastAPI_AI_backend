from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from ..db.mongo import users_collection
from ..utils.auth_utils import get_current_user    # adjust import to your project

router = APIRouter(prefix="/eula", tags=["EULA"])

@router.post("/accept")
async def accept_eula(user=Depends(get_current_user)):
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"eula.accepted": True, "eula.accepted_at": datetime.utcnow()}}
    )
    return {"ok": True}

async def require_eula(user=Depends(get_current_user)):
    if not user.get("eula", {}).get("accepted", False):
        raise HTTPException(status_code=403, detail="Please accept EULA to use UGC features.")
    return user
