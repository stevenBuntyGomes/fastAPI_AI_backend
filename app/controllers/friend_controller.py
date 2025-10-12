# app/controllers/friend_controller.py
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException

from ..schemas.friend import (
    FriendCreate,
    FriendUpdate,
    FriendResponse,
    FriendRequestSend,
    FriendRequestAct,
    FriendRequestListQuery,
    FriendRequestResponse,
    UnfriendRequest,
)
from ..db.mongo import (
    friend_collection,
    friend_requests_collection,   # <-- REQUIRED for requests
    users_collection,
    mypod_collection,
    recovery_collection,
)
from .mypod_controller import upsert_friend_in_mypod  # keep existing wiring

# -----------------------------
# Helpers
# -----------------------------
def _as_oid(v: str) -> ObjectId:
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format.")

async def _user_exists(oid: ObjectId) -> bool:
    return await users_collection.find_one({"_id": oid}, {"_id": 1}) is not None

async def _lookup_friend_defaults(friend_user_oid: ObjectId) -> dict:
    """
    Pull default values for friend fields from backend sources:
      - aura: users_collection.aura
      - login_streak: mypod_collection.login_streak
      - quit_date: recovery_collection.quit_date (if exists)
    """
    user_doc = await users_collection.find_one({"_id": friend_user_oid}) or {}
    mypod_doc = await mypod_collection.find_one({"user_id": friend_user_oid}) or {}
    recovery_doc = await recovery_collection.find_one({"user_id": friend_user_oid}) or {}

    aura = int(user_doc.get("aura", 0))
    login_streak = int(mypod_doc.get("login_streak", 0))
    quit_date = recovery_doc.get("quit_date")  # ok if None

    return {"aura": aura, "login_streak": login_streak, "quit_date": quit_date}

async def _remove_friend_in_mypod(owner_user_id: str, friend_user_id: str) -> None:
    """
    Best-effort removal from MyPod friends list for various shapes.
    """
    owner_oid = _as_oid(owner_user_id)

    # Array of objects: { friend_id: "<id>", ... }
    await mypod_collection.update_one(
        {"user_id": owner_oid},
        {"$pull": {"friends_list": {"friend_id": str(friend_user_id)}}}
    )
    # Array of plain strings
    await mypod_collection.update_one(
        {"user_id": owner_oid},
        {"$pull": {"friends_list": str(friend_user_id)}}
    )
    # Array of ObjectIds
    try:
        await mypod_collection.update_one(
            {"user_id": owner_oid},
            {"$pull": {"friends_list": _as_oid(friend_user_id)}}
        )
    except HTTPException:
        pass

# -----------------------------
# Friend Profile (existing)
# -----------------------------
async def create_friend_profile(user: dict, data: FriendCreate) -> FriendResponse:
    owner_oid = _as_oid(str(user["_id"]))
    friend_user_oid = _as_oid(str(data.friend_id))

    # Ensure friend user exists
    if not await _user_exists(friend_user_oid):
        raise HTTPException(status_code=404, detail="Friend user not found.")

    # Derive backend defaults
    defaults = await _lookup_friend_defaults(friend_user_oid)

    # Prepare payload
    body = data.dict()
    body["friends_list"] = [str(_as_oid(fid)) for fid in body.get("friends_list", [])]

    # Ownership + timestamps
    body["user_id"] = str(owner_oid)
    body["created_at"] = datetime.utcnow()
    body["updated_at"] = datetime.utcnow()

    # Auto-fill fields if missing
    body["friend_aura"] = (
        data.friend_aura if data.friend_aura is not None else defaults["aura"]
    )
    body["friend_login_streak"] = (
        data.friend_login_streak if data.friend_login_streak is not None else defaults["login_streak"]
    )
    if data.friend_quit_date is None and defaults["quit_date"] is not None:
        body["friend_quit_date"] = defaults["quit_date"]

    # Insert
    try:
        result = await friend_collection.insert_one(body)
    except Exception as e:
        if "E11000" in str(e):
            # Unique (user_id, friend_id) index will throw this; treat as already exists
            raise HTTPException(status_code=409, detail="Friend profile already exists.")
        raise

    body["id"] = str(result.inserted_id)

    # Keep MyPod in sync
    await upsert_friend_in_mypod(str(owner_oid), str(friend_user_oid))

    return FriendResponse(**body)

async def get_friend_profiles(user: dict) -> List[FriendResponse]:
    user_id = str(user["_id"])
    cursor = friend_collection.find({"user_id": user_id})
    profiles = []
    async for profile in cursor:
        profile["id"] = str(profile["_id"])
        profile["user_id"] = str(profile["user_id"])
        profile["friends_list"] = [str(fid) for fid in profile.get("friends_list", [])]
        profiles.append(FriendResponse(**profile))
    return profiles

async def get_friend_profile_by_id(friend_id: str, user: dict) -> FriendResponse:
    try:
        obj_id = ObjectId(friend_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid friend ID format.")

    profile = await friend_collection.find_one({"_id": obj_id, "user_id": str(user["_id"])})
    if not profile:
        raise HTTPException(status_code=404, detail="Friend profile not found.")

    profile["id"] = str(profile["_id"])
    profile["user_id"] = str(profile["user_id"])
    profile["friends_list"] = [str(fid) for fid in profile.get("friends_list", [])]
    return FriendResponse(**profile)

async def update_friend_profile(friend_id: str, data: FriendUpdate, user: dict) -> FriendResponse:
    try:
        obj_id = ObjectId(friend_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid friend ID format.")

    update_data = {k: v for k, v in data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    result = await friend_collection.update_one(
        {"_id": obj_id, "user_id": str(user["_id"])},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Update failed or no changes made.")

    updated = await friend_collection.find_one({"_id": obj_id})
    updated["id"] = str(updated["_id"])
    updated["user_id"] = str(updated["user_id"])
    updated["friends_list"] = [str(fid) for fid in updated.get("friends_list", [])]
    return FriendResponse(**updated)

async def delete_friend_profile(friend_id: str, user: dict) -> dict:
    try:
        obj_id = ObjectId(friend_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid friend ID format.")

    result = await friend_collection.delete_one({"_id": obj_id, "user_id": str(user["_id"])})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Friend profile not found or already deleted.")

    return {"message": "🗑️ Friend profile deleted."}

async def get_all_friend_profiles():
    cursor = friend_collection.find()
    results = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        doc["user_id"] = str(doc["user_id"])
        doc["friends_list"] = [str(fid) for fid in doc.get("friends_list", [])]
        results.append(FriendResponse(**doc))
    return results

# -----------------------------
# Friend Requests
# -----------------------------
REQUEST_STATUSES = ("pending", "accepted", "rejected", "canceled")

async def send_friend_request(user: dict, payload: FriendRequestSend) -> FriendRequestResponse:
    from_oid = _as_oid(str(user["_id"]))
    to_oid = _as_oid(payload.to_user_id)

    if from_oid == to_oid:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself.")
    if not await _user_exists(to_oid):
        raise HTTPException(status_code=404, detail="Recipient user not found.")

    # Check for existing pending either direction
    existing = await friend_requests_collection.find_one({
        "$or": [
            {"from_user_id": str(from_oid), "to_user_id": str(to_oid), "status": "pending"},
            {"from_user_id": str(to_oid), "to_user_id": str(from_oid), "status": "pending"},
        ]
    })
    if existing:
        raise HTTPException(status_code=409, detail="A pending request already exists between these users.")

    # Already friends?
    already = await friend_requests_collection.find_one({
        "$or": [
            {"from_user_id": str(from_oid), "to_user_id": str(to_oid), "status": "accepted"},
            {"from_user_id": str(to_oid), "to_user_id": str(from_oid), "status": "accepted"},
        ]
    })
    if already:
        raise HTTPException(status_code=409, detail="Users are already friends.")

    doc = {
        "from_user_id": str(from_oid),
        "to_user_id": str(to_oid),
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await friend_requests_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return FriendRequestResponse(**doc)

async def accept_friend_request(user: dict, payload: FriendRequestAct) -> FriendRequestResponse:
    req_oid = _as_oid(payload.request_id)
    me = str(user["_id"])

    request = await friend_requests_collection.find_one({"_id": req_oid})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if request["to_user_id"] != me:
        raise HTTPException(status_code=403, detail="You can only accept requests sent to you.")
    if request["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot accept a '{request['status']}' request.")

    await friend_requests_collection.update_one(
        {"_id": req_oid},
        {"$set": {"status": "accepted", "updated_at": datetime.utcnow()}}
    )

    # On accept: create FriendProfile for both sides (idempotent)
    from_id = request["from_user_id"]
    to_id = request["to_user_id"]

    try:
        await create_friend_profile({"_id": to_id}, FriendCreate(friend_id=from_id))
    except HTTPException as e:
        if e.status_code != 409:
            raise
    try:
        await create_friend_profile({"_id": from_id}, FriendCreate(friend_id=to_id))
    except HTTPException as e:
        if e.status_code != 409:
            raise

    # MyPod sync both ways (create_friend_profile already updates owner side)
    await upsert_friend_in_mypod(to_id, from_id)
    await upsert_friend_in_mypod(from_id, to_id)

    updated = await friend_requests_collection.find_one({"_id": req_oid})
    updated["id"] = str(updated["_id"])
    return FriendRequestResponse(**updated)

async def reject_friend_request(user: dict, payload: FriendRequestAct) -> FriendRequestResponse:
    req_oid = _as_oid(payload.request_id)
    me = str(user["_id"])

    request = await friend_requests_collection.find_one({"_id": req_oid})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if request["to_user_id"] != me:
        raise HTTPException(status_code=403, detail="You can only reject requests sent to you.")
    if request["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot reject a '{request['status']}' request.")

    await friend_requests_collection.update_one(
        {"_id": req_oid},
        {"$set": {"status": "rejected", "updated_at": datetime.utcnow()}}
    )

    updated = await friend_requests_collection.find_one({"_id": req_oid})
    updated["id"] = str(updated["_id"])
    return FriendRequestResponse(**updated)

async def cancel_friend_request(user: dict, payload: FriendRequestAct) -> FriendRequestResponse:
    req_oid = _as_oid(payload.request_id)
    me = str(user["_id"])

    request = await friend_requests_collection.find_one({"_id": req_oid})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found.")
    if request["from_user_id"] != me:
        raise HTTPException(status_code=403, detail="You can only cancel requests you sent.")
    if request["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot cancel a '{request['status']}' request.")

    await friend_requests_collection.update_one(
        {"_id": req_oid},
        {"$set": {"status": "canceled", "updated_at": datetime.utcnow()}}
    )

    updated = await friend_requests_collection.find_one({"_id": req_oid})
    updated["id"] = str(updated["_id"])
    return FriendRequestResponse(**updated)

async def list_friend_requests(user: dict, query: FriendRequestListQuery) -> List[FriendRequestResponse]:
    me = str(user["_id"])
    q: dict = {}

    if query.role == "received":
        q["to_user_id"] = me
    elif query.role == "sent":
        q["from_user_id"] = me
    else:
        q["$or"] = [{"to_user_id": me}, {"from_user_id": me}]

    if query.status:
        if query.status not in REQUEST_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter.")
        q["status"] = query.status

    cursor = friend_requests_collection.find(q).sort("created_at", -1).skip(query.skip).limit(query.limit)
    out: List[FriendRequestResponse] = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        out.append(FriendRequestResponse(**doc))
    return out

# -----------------------------
# UNFRIEND (NEW)
# -----------------------------
async def unfriend(user: dict, payload: UnfriendRequest) -> dict:
    """
    Remove friendship both ways:
      - delete FriendProfile where (user_id = me, friend_id = them)
      - delete FriendProfile where (user_id = them, friend_id = me)
      - remove MyPod links in both directions
    """
    me_id = str(user["_id"])
    friend_id = payload.friend_user_id
    _ = _as_oid(me_id)       # validate
    _ = _as_oid(friend_id)   # validate

    if not await _user_exists(_as_oid(friend_id)):
        raise HTTPException(status_code=404, detail="Friend user not found.")

    # Delete friend profiles both ways (best-effort)
    await friend_collection.delete_many({"user_id": me_id, "friend_id": friend_id})
    await friend_collection.delete_many({"user_id": friend_id, "friend_id": me_id})

    # Remove MyPod links both ways (best-effort)
    await _remove_friend_in_mypod(me_id, friend_id)
    await _remove_friend_in_mypod(friend_id, me_id)

    # Keep friend_requests history (no deletion)
    return {"message": "👋 Unfriended successfully."}
