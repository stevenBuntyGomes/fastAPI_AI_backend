# app/bump.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from typing import Optional
from app.db.mongo import devices_collection
from app.services.apns_service import send_apns_push
import sys, traceback

router = APIRouter(prefix="/bump", tags=["bump"])

class BumpBody(BaseModel):
    to_user_id: str
    message: str = "🔔 Bump!"

@router.post("")
async def send_bump(body: BumpBody):
    try:
        to_oid = ObjectId(body.to_user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid to_user_id")

    d: Optional[dict] = await devices_collection.find_one({"user_id": to_oid, "platform": "ios"})
    if not d or not d.get("token"):
        return {"ok": True, "sent": 0, "note": "No iOS device for user"}

    env = str(d.get("environment", "production")).lower()
    if env not in ("production", "sandbox"):
        env = "production"

    try:
        res = await send_apns_push(
            token_hex=d["token"],
            env=env,
            alert={"title": "Breathr", "body": body.message},
            push_type="alert",
            thread_id="bump",
            category="BUMP"
        )
    except Exception as e:
        print("❌ APNs send error:", repr(e), file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="APNs send failed")

    if not res["ok"]:
        status = res.get("status")
        reason = (res.get("body") or {}).get("reason")
        if status in (400, 410) and reason in ("BadDeviceToken", "Unregistered"):
            await devices_collection.delete_one({"_id": d["_id"]})
            return {"ok": False, "sent": 0, "pruned": 1, "apns": res}
        return {"ok": False, "sent": 0, "apns": res}

    return {"ok": True, "sent": 1, "apns": {"status": res["status"], "body": res.get("body")}}
