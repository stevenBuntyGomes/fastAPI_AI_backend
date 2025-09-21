# app/services/socket_manager.py
import os
import jwt
import socketio
from typing import Dict, Set, Any, Optional, List
from datetime import datetime
from urllib.parse import parse_qs

from bson import ObjectId
from app.db.mongo import (
    users_collection,
    socket_sessions_collection,
    devices_collection,
    bumps_collection,
)

# ------------------------
# Config
# ------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

# Comma-separated list of origins, e.g. "https://nevermindbro.com,https://app.nevermindbro.com"
_raw_origins = os.getenv("SOCKETIO_CORS_ORIGINS", "*").strip()
if _raw_origins == "*" or not _raw_origins:
    CORS_ORIGINS = "*"
else:
    CORS_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Use this when mounting ASGIApp in main.py:
#   app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path=SOCKETIO_PATH.lstrip('/'))
SOCKETIO_PATH = os.getenv("SOCKETIO_PATH", "/socket.io")

# ------------------------
# In-memory maps
# ------------------------
user_to_sids: Dict[str, Set[str]] = {}
sid_to_user: Dict[str, str] = {}

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=CORS_ORIGINS,
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
    if user_id in user_to_sids and user_to_sids[user_id]:
        return list(user_to_sids[user_id])
    cursor = socket_sessions_collection.find({"user_id": user_id})
    return [doc["sid"] async for doc in cursor]

async def emit_to_user(user_id: str, event: str, payload: Any) -> int:
    delivered = 0
    for sid in await get_user_sids(user_id):
        await sio.emit(event, payload, to=sid)
        delivered += 1
    return delivered

def _decode_jwt(maybe_token: Optional[str]) -> Optional[str]:
    if not maybe_token:
        return None
    try:
        payload = jwt.decode(maybe_token, JWT_SECRET, algorithms=[JWT_ALG])
        uid = payload.get("user_id") or payload.get("sub")
        return str(uid) if uid else None
    except Exception:
        return None

def _get_token_from_environ(environ: dict) -> Optional[str]:
    # Authorization: Bearer <token>
    authz = environ.get("HTTP_AUTHORIZATION") or environ.get("Authorization")
    if authz and isinstance(authz, str):
        parts = authz.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

    # Query string ?token=... or ?jwt=... or ?access_token=...
    qs = parse_qs(environ.get("QUERY_STRING", "") or "")
    for key in ("token", "jwt", "access_token"):
        vals = qs.get(key)
        if vals and len(vals) > 0 and vals[0]:
            return vals[0]
    return None

def _extract_user_id_from_connect(environ: dict, auth: Optional[dict]) -> Optional[str]:
    """
    Accept JWT from:
      1) JS-style auth dict: auth = {"token": "<JWT>"} or {"jwt": "<JWT>"}
      2) Query string: ?token=... / ?jwt=... / ?access_token=...
      3) Authorization header: Bearer <JWT>
    (Optionally accepts auth = {"user_id": "<id>"} for trusted contexts.)
    """
    # 1) auth dict
    if isinstance(auth, dict):
        token = auth.get("token") or auth.get("jwt")
        uid = _decode_jwt(token)
        if uid:
            return uid
        # trusted fallback (avoid using this from untrusted clients)
        raw_uid = auth.get("user_id")
        if raw_uid:
            return str(raw_uid)

    # 2) Authorization header / query string
    token = _get_token_from_environ(environ)
    uid = _decode_jwt(token)
    if uid:
        return uid

    return None

# ------------------------
# Lifecycle events
# ------------------------
@sio.event
async def connect(sid, environ, auth):
    """
    Swift example (Socket.IO-Client-Swift):
      let manager = SocketManager(
        socketURL: URL(string: "https://api.nevermindbro.com")!,
        config: [.path("/socket.io"), .forceWebsockets(true),
                 .connectParams(["token": "<JWT>"]), .compress, .log(true)]
      )
    """
    user_id = _extract_user_id_from_connect(environ, auth)
    if not user_id:
        return False

    if not ObjectId.is_valid(user_id):
        return False
    if not await users_collection.find_one({"_id": ObjectId(user_id)}):
        return False

    sid_to_user[sid] = user_id
    user_to_sids.setdefault(user_id, set()).add(sid)

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
# Bump event (core)
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

        if not ObjectId.is_valid(to_user_id) or not await users_collection.find_one({"_id": ObjectId(to_user_id)}):
            return await sio.emit("bump_ack", {"ok": False, "reason": "target_not_found"}, to=sid)

        bump_doc = {
            "from_user_id": sender_id,
            "to_user_id": str(to_user_id),
            "message": message,
            "created_at": datetime.utcnow(),
            "delivery": {"sockets_delivered": 0, "fallback_push": False},
        }
        result = await bumps_collection.insert_one(bump_doc)

        payload = {
            "type": "bump",
            "message": message,
            "from": sender_id,
            "bump_id": str(result.inserted_id),
            "created_at": bump_doc["created_at"].isoformat() + "Z",
        }
        delivered = await emit_to_user(str(to_user_id), "bump", payload)

        await bumps_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"delivery.sockets_delivered": delivered}}
        )

        # (Optional) If delivered == 0, look up devices in devices_collection and trigger APNs.

        await sio.emit(
            "bump_ack",
            {"ok": True, "to": str(to_user_id), "delivered": delivered, "bump_id": str(result.inserted_id)},
            to=sid,
        )
    except Exception as e:
        await sio.emit("bump_ack", {"ok": False, "error": str(e)}, to=sid)

__all__ = ["sio", "emit_to_user", "SOCKETIO_PATH"]
