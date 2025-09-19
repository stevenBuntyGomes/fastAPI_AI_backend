# app/services/socket_manager.py
import os
import jwt
import socketio
from typing import Dict, Set, Any, Optional, List
from datetime import datetime
from bson import ObjectId

from app.db.mongo import (
    users_collection,
    socket_sessions_collection,
    devices_collection,    # ensure in mongo.py
    bumps_collection,      # ensure in mongo.py
)

JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

# In-memory connection maps
user_to_sids: Dict[str, Set[str]] = {}
sid_to_user: Dict[str, str] = {}

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=60,
)

# ------------------------
# Helpers
# ------------------------
async def _persist_session(user_id: str, sid: str) -> None:
    await socket_sessions_collection.update_one(
        {"sid": sid},
        {"$set": {"sid": sid, "user_id": user_id, "connected_at": datetime.utcnow()}},
        upsert=True,
    )

async def _remove_session(sid: str) -> None:
    await socket_sessions_collection.delete_one({"sid": sid})

async def get_user_sids(user_id: str) -> List[str]:
    # Fast path: in-memory
    if user_id in user_to_sids and user_to_sids[user_id]:
        return list(user_to_sids[user_id])
    # Fallback: DB (e.g., after app restart)
    cursor = socket_sessions_collection.find({"user_id": user_id})
    return [doc["sid"] async for doc in cursor]

async def emit_to_user(user_id: str, event: str, payload: Any) -> int:
    delivered = 0
    for sid in await get_user_sids(user_id):
        await sio.emit(event, payload, to=sid)
        delivered += 1
    return delivered

def _extract_user_id_from_auth(auth: Optional[dict]) -> Optional[str]:
    """
    Accept either:
      - auth = {"token": "<JWT>"} -> decode -> user_id/sub
      - auth = {"user_id": "<id>"} (only in trusted scenarios)
    """
    if not auth or not isinstance(auth, dict):
        return None

    token = auth.get("token")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
            uid = payload.get("user_id") or payload.get("sub")
            return str(uid) if uid else None
        except Exception:
            return None

    uid = auth.get("user_id")
    return str(uid) if uid else None

# ------------------------
# Lifecycle events
# ------------------------
@sio.event
async def connect(sid, environ, auth):
    user_id = _extract_user_id_from_auth(auth)
    if not user_id:
        return False

    # Validate ObjectId and user exists
    if not ObjectId.is_valid(user_id):
        return False
    if not await users_collection.find_one({"_id": ObjectId(user_id)}):
        return False

    # Map connections
    sid_to_user[sid] = user_id
    user_to_sids.setdefault(user_id, set()).add(sid)

    # Persist session
    await _persist_session(user_id, sid)
    return True

@sio.event
async def disconnect(sid):
    user_id = sid_to_user.pop(sid, None)
    await _remove_session(sid)
    if user_id and user_id in user_to_sids:
        user_to_sids[user_id].discard(sid)
        if not user_to_sids[user_id]:
            user_to_sids.pop(user_id, None)

# ------------------------
# Optional: register APNs token for offline push fallback
# ------------------------
@sio.on("register_device")
async def register_device(sid, data):
    """
    Swift (once after connect):
      socket.emit("register_device", { "apns_token": "<token>", "platform": "ios" })
    """
    try:
        user_id = sid_to_user.get(sid)
        if not user_id:
            return await sio.emit("register_device_ack", {"ok": False, "reason": "unauthenticated"}, to=sid)

        apns_token = (data or {}).get("apns_token")
        platform = (data or {}).get("platform", "ios")
        if not apns_token:
            return await sio.emit("register_device_ack", {"ok": False, "reason": "missing_token"}, to=sid)

        await devices_collection.update_one(
            {"user_id": user_id, "platform": platform},
            {"$set": {
                "user_id": user_id,
                "platform": platform,
                "apns_token": apns_token,
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )
        await sio.emit("register_device_ack", {"ok": True}, to=sid)
    except Exception as e:
        await sio.emit("register_device_ack", {"ok": False, "error": str(e)}, to=sid)

# ------------------------
# Bump event (core) — THIS is where emit_to_user(...) lives
# ------------------------
@sio.on("bump")
async def bump(sid, data):
    """
    Swift emits:
      socket.emit("bump", { "to": "<target_user_id>", "message": "Yo!" })
    """
    try:
        sender_id = sid_to_user.get(sid)
        if not sender_id:
            return await sio.emit("bump_ack", {"ok": False, "reason": "unauthenticated"}, to=sid)

        to_user_id = (data or {}).get("to")
        message = (data or {}).get("message") or "🔔 Bump!"
        if not to_user_id:
            return await sio.emit("bump_ack", {"ok": False, "reason": "missing_to_user_id"}, to=sid)

        # Optional: ensure target exists if you use Mongo ObjectIds for users
        if not ObjectId.is_valid(to_user_id) or not await users_collection.find_one({"_id": ObjectId(to_user_id)}):
            return await sio.emit("bump_ack", {"ok": False, "reason": "target_not_found"}, to=sid)

        # 1) Persist bump (source of truth)
        bump_doc = {
            "from_user_id": sender_id,
            "to_user_id": str(to_user_id),
            "message": message,
            "created_at": datetime.utcnow(),
            "delivery": {"sockets_delivered": 0, "fallback_push": False},
        }
        result = await bumps_collection.insert_one(bump_doc)

        # 2) Deliver live over sockets  ⬅️ EXACT SPOT for emit_to_user(...)
        payload = {
            "type": "bump",
            "message": message,
            "from": sender_id,
            "bump_id": str(result.inserted_id),
            "created_at": bump_doc["created_at"].isoformat() + "Z",
        }
        delivered = await emit_to_user(str(to_user_id), "bump", payload)

        # 3) Update delivery stats on the bump record
        await bumps_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"delivery.sockets_delivered": delivered}}
        )

        # 4) (Optional) If delivered == 0, trigger APNs push using devices_collection
        #    -> Look up devices by user_id and send via your push provider here.

        # 5) ACK back to sender
        await sio.emit(
            "bump_ack",
            {"ok": True, "to": str(to_user_id), "delivered": delivered, "bump_id": str(result.inserted_id)},
            to=sid,
        )
    except Exception as e:
        await sio.emit("bump_ack", {"ok": False, "error": str(e)}, to=sid)

# Exported for use elsewhere (server-initiated emits)
__all__ = ["sio", "emit_to_user"]