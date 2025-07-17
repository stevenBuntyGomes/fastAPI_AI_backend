from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from ..db.mongo import friend_collection
from ..schemas.friend import FriendCreate, FriendUpdate, FriendResponse


# ✅ Create friend profile
async def create_friend_profile(user: dict, data: FriendCreate):
    friend_dict = data.dict()
    friend_dict["user_id"] = str(user["_id"])
    friend_dict["created_at"] = datetime.utcnow()
    friend_dict["updated_at"] = datetime.utcnow()

    result = await friend_collection.insert_one(friend_dict)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create friend profile.")

    friend_dict["id"] = str(result.inserted_id)
    return FriendResponse(**friend_dict)



# ✅ Get all friend profiles for a user
async def get_friend_profiles(user: dict) -> list[FriendResponse]:
    user_id = str(user["_id"])
    cursor = friend_collection.find({"user_id": user_id})
    profiles = []
    async for profile in cursor:
        profile["id"] = str(profile["_id"])
        profile["user_id"] = str(profile["user_id"])
        profile["friends_list"] = [str(fid) for fid in profile.get("friends_list", [])]
        profiles.append(FriendResponse(**profile))
    return profiles


# ✅ Get single friend profile
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


# ✅ Update friend profile
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


# ✅ Delete friend profile
async def delete_friend_profile(friend_id: str, user: dict) -> dict:
    try:
        obj_id = ObjectId(friend_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid friend ID format.")

    result = await friend_collection.delete_one({"_id": obj_id, "user_id": str(user["_id"])})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Friend profile not found or already deleted.")

    return {"message": "🗑️ Friend profile deleted."}


# ✅ List all friend profiles (admin/test route)
async def get_all_friend_profiles() -> list[FriendResponse]:
    cursor = friend_collection.find()
    results = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        doc["user_id"] = str(doc["user_id"])
        doc["friends_list"] = [str(fid) for fid in doc.get("friends_list", [])]
        results.append(FriendResponse(**doc))
    return results
