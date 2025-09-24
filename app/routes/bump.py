# app/bump.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from typing import Optional, List, Dict, Any
import sys, traceback

from app.db.mongo import devices_collection
from app.services.apns_service import send_apns_push

router = APIRouter(prefix="/bump", tags=["bump"])

class BumpBody(BaseModel):
    to_user_id: str
    message: str = "🔔 Bump!"

@router.post("")
async def send_bump(body: BumpBody) -> Dict[str, Any]:
    # 1) validate user id
    try:
        to_oid = ObjectId(body.to_user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid to_user_id")

    # 2) fetch ALL iOS devices for the user (support multi-device gracefully)
    devices: List[dict] = await devices_collection.find(
        {"user_id": to_oid, "platform": "ios"},
        projection={"token": 1, "environment": 1}
    ).to_list(None)

    if not devices:
        return {"ok": True, "sent": 0, "failed": 0, "pruned": 0, "results": [], "note": "No iOS device for user"}

    # 3) send to each device, collect results; prune bad tokens
    sent = 0
    failed = 0
    pruned = 0
    results: List[Dict[str, Any]] = []
    to_prune_ids: List[ObjectId] = []

    for d in devices:
        token: Optional[str] = d.get("token")
        if not token:
            failed += 1
            results.append({
                "token_prefix": None,
                "env": None,
                "ok": False,
                "status": 0,
                "reason": "MissingToken"
            })
            continue

        env = str((d.get("environment") or "production")).lower()
        env = "production" if env == "production" else "sandbox"

        try:
            res = await send_apns_push(
                token_hex=token,
                env=env,
                alert={"title": "Breathr", "body": body.message},
                push_type="alert",
                thread_id="bump",
                category="BUMP"
            )
        except Exception as e:
            # Never 500: capture and return the error context
            print("❌ APNs send error:", repr(e), file=sys.stderr)
            traceback.print_exc()
            failed += 1
            results.append({
                "token_prefix": token[:8],
                "env": env,
                "ok": False,
                "status": 0,
                "reason": "Exception",
                "error": str(e),
            })
            continue

        # classify result
        ok = bool(res.get("ok"))
        status = res.get("status")
        body_obj = (res.get("body") or {})
        reason = body_obj.get("reason") or body_obj.get("text")

        if ok:
            sent += 1
        else:
            failed += 1
            # prune known-permanent failures
            if status in (400, 410) and reason in ("BadDeviceToken", "Unregistered"):
                # fetch _id to delete; quicker to requery by token
                doc = await devices_collection.find_one({"user_id": to_oid, "platform": "ios", "token": token}, {"_id": 1})
                if doc and doc.get("_id"):
                    to_prune_ids.append(doc["_id"])

        results.append({
            "token_prefix": token[:8],
            "env": env,
            "ok": ok,
            "status": status,
            "reason": reason,
            "apns": body_obj if not ok else {"note": "Delivered"},
        })

    # 4) prune dead tokens (if any)
    if to_prune_ids:
        del_res = await devices_collection.delete_many({"_id": {"$in": to_prune_ids}})
        pruned = int(del_res.deleted_count or 0)

    # 5) final summary (never raises)
    return {
        "ok": sent > 0,          # true if at least one device received the bump
        "sent": sent,
        "failed": failed,
        "pruned": pruned,
        "results": results
    }
