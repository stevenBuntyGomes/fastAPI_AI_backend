# app/routes/bump.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

from app.db.mongo import (
    users_collection,
    devices_collection,
    bumps_collection,
)
from app.services.apns_service import send_apns_push
from app.utils.auth_utils import get_current_user  # your existing auth dependency

router = APIRouter(prefix="/bump", tags=["bump"])


class BumpBody(BaseModel):
    to_user_id: str
    message: Optional[str] = "🔔 Bump!"


@router.post("")
async def send_bump(
    body: BumpBody,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Send a bump to another user via APNs (no Socket.IO).

    iOS should call:

        POST /bump
        Authorization: Bearer <JWT>
        {
          "to_user_id": "<target Mongo _id as string>",
          "message": "Hey, you got this! 💜"
        }
    """
    # 1) validate & load target user
    if not ObjectId.is_valid(body.to_user_id):
        raise HTTPException(status_code=400, detail="Invalid to_user_id")

    to_oid = ObjectId(body.to_user_id)
    from_oid = ObjectId(current_user["_id"])

    target_user = await users_collection.find_one({"_id": to_oid}, {"_id": 1})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    message = body.message or "🔔 Bump!"

    # 2) persist bump record (for history / analytics)
    bump_doc = {
        "from_user_id": from_oid,
        "to_user_id": to_oid,
        "message": message,
        "created_at": datetime.utcnow(),
        "via": "rest",
    }
    insert_res = await bumps_collection.insert_one(bump_doc)

    # 3) find all iOS devices for the target user
    #    Support both ObjectId and legacy string user_id docs just in case
    devices: List[dict] = await devices_collection.find(
        {"user_id": {"$in": [to_oid, body.to_user_id]}, "platform": "ios"},
        projection={"token": 1, "environment": 1},
    ).to_list(None)

    # Fallback: if no device docs, try users.apns_token
    if not devices:
        user_doc = await users_collection.find_one({"_id": to_oid}, {"apns_token": 1})
        token = user_doc.get("apns_token") if user_doc else None
        if token:
            devices = [{"token": token, "environment": "production"}]

    if not devices:
        return {
            "ok": False,
            "sent": 0,
            "failed": 0,
            "pruned": 0,
            "results": [],
            "note": "No APNs token registered for user",
        }

    # 4) send APNs to each device, prune dead tokens
    sent = 0
    failed = 0
    pruned = 0
    results: List[Dict[str, Any]] = []
    to_prune_ids: List[ObjectId] = []

    for d in devices:
        token: Optional[str] = d.get("token")
        if not token:
            failed += 1
            results.append(
                {
                    "token_prefix": None,
                    "env": None,
                    "ok": False,
                    "status": 0,
                    "reason": "MissingToken",
                }
            )
            continue

        env_raw = str((d.get("environment") or "production")).lower()
        env = "production" if env_raw == "production" else "sandbox"

        res = await send_apns_push(
            token_hex=token,
            env=env,
            alert={"title": "Breathr", "body": message},
            push_type="alert",
            thread_id="bump",
            category="BUMP",
        )

        ok = bool(res.get("ok"))
        status = res.get("status")
        body_obj = res.get("body") or {}
        reason = body_obj.get("reason") or body_obj.get("text")

        if ok:
            sent += 1
        else:
            failed += 1
            # Permanent token errors → delete those device docs
            if status in (400, 410) and reason in ("BadDeviceToken", "Unregistered"):
                doc_id = d.get("_id")
                if isinstance(doc_id, ObjectId):
                    to_prune_ids.append(doc_id)

        results.append(
            {
                "token_prefix": token[:8],
                "env": env,
                "ok": ok,
                "status": status,
                "reason": reason,
                "apns": body_obj if not ok else {"note": "Delivered"},
            }
        )

    if to_prune_ids:
        del_res = await devices_collection.delete_many({"_id": {"$in": to_prune_ids}})
        pruned = int(del_res.deleted_count or 0)

    return {
        "ok": sent > 0,
        "sent": sent,
        "failed": failed,
        "pruned": pruned,
        "results": results,
        "bump_id": str(insert_res.inserted_id),
    }
