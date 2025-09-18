# app/controllers/friend_controller.py
from datetime import datetime
from typing import List
from bson import ObjectId
from fastapi import HTTPException

from ..schemas.friend import FriendCreate, FriendUpdate, FriendResponse
from ..db.mongo import (
    friend_collection,
    users_collection,
    mypod_collection,
    recovery_collection,
)
from .mypod_controller import upsert_friend_in_mypod  # you already have MyPod wiring

def _as_oid(v: str) -> ObjectId:
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format.")

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
    quit_date = recovery_doc.get("quit_date")  # ok if None / missing

    return {"aura": aura, "login_streak": login_streak, "quit_date": quit_date}

# ✅ Create friend profile (auto-fill the three fields) + keep MyPod in sync
async def create_friend_profile(user: dict, data: FriendCreate) -> FriendResponse:
    owner_oid = _as_oid(str(user["_id"]))
    friend_user_oid = _as_oid(str(data.friend_id))

    # Ensure friend user exists
    friend_user = await users_collection.find_one({"_id": friend_user_oid})
    if not friend_user:
        raise HTTPException(status_code=404, detail="Friend user not found.")

    # Derive backend defaults
    defaults = await _lookup_friend_defaults(friend_user_oid)

    # Prepare payload
    body = data.dict()
    # normalize any friends_list entries to strings
    body["friends_list"] = [str(_as_oid(fid)) for fid in body.get("friends_list", [])]

    # Ownership + timestamps
    body["user_id"] = str(owner_oid)
    body["created_at"] = datetime.utcnow()
    body["updated_at"] = datetime.utcnow()

    # Auto-fill the three fields if not provided by client
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
            raise HTTPException(status_code=409, detail="Friend profile already exists.")
        raise

    body["id"] = str(result.inserted_id)

    # Keep MyPod.friends_list in sync (already part of your design)
    # — adds/refreshes an entry for this friend in the caller's MyPod
    await upsert_friend_in_mypod(str(owner_oid), str(friend_user_oid))

    return FriendResponse(**body)

# ✅ The rest can remain unchanged
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
