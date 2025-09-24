# app/bump.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from typing import Optional
from app.db.mongo import devices_collection
from app.services.apns_client import send_apns_push

router = APIRouter(prefix="/bump", tags=["bump"])

class BumpBody(BaseModel):
    to_user_id: str
    message: str = "🔔 Bump!"

@router.post("")
async def send_bump(body: BumpBody):
    # validate target
    try:
        to_oid = ObjectId(body.to_user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid to_user_id")

    # fetch that user's iOS token (one per your rule)
    d: Optional[dict] = await devices_collection.find_one({"user_id": to_oid, "platform": "ios"})
    if not d or not d.get("token"):
        return {"ok": True, "sent": 0, "note": "No iOS device for user"}

    res = await send_apns_push(
        token_hex=d["token"],
        env=(d.get("environment") or "production").lower(),
        alert={"title": "Breathr", "body": body.message},
        push_type="alert",
        thread_id="bump",
        category="BUMP"
    )

    # Optional: if token is dead, remove it
    if not res["ok"]:
        if res.get("status") in (400, 410) and (res.get("body", {}).get("reason") in ("BadDeviceToken", "Unregistered")):
            await devices_collection.delete_one({"_id": d["_id"]})
            return {"ok": False, "sent": 0, "pruned": 1, "apns": res}

    return {"ok": True, "sent": 1, "apns": {"status": res["status"], "body": res.get("body")}}
