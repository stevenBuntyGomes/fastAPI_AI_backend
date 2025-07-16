from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from ..db.mongo import friend_collection
from ..models.friend_model import FriendProfileModel
from ..schemas.friend import FriendCreate, FriendUpdate, FriendResponse


# ✅ Create friend profile
async def create_friend_profile(data: FriendCreate, user: dict):
    friend_dict = data.dict()
    friend_dict["user_id"] = str(user["_id"])
    friend_dict["created_at"] = datetime.utcnow()
    friend_dict["updated_at"] = datetime.utcnow()

    result = await friend_collection.insert_one(friend_dict)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create friend profile.")

    return {"message": "✅ Friend profile created", "id": str(result.inserted_id)}


# ✅ Get all friend profiles for a user
async def get_friend_profiles(user: dict):
    user_id = str(user["_id"])
    cursor = friend_collection.find({"user_id": user_id})
    profiles = []
    async for profile in cursor:
        profile["_id"] = str(profile["_id"])
        profiles.append(profile)
    return profiles


# ✅ Get single friend profile
async def get_friend_profile_by_id(friend_id: str, user: dict):
    profile = await friend_collection.find_one({"_id": ObjectId(friend_id), "user_id": str(user["_id"])})
    if not profile:
        raise HTTPException(status_code=404, detail="Friend profile not found.")
    profile["_id"] = str(profile["_id"])
    return profile


# ✅ Update friend profile
async def update_friend_profile(friend_id: str, data: FriendUpdate, user: dict):
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    result = await friend_collection.update_one(
        {"_id": ObjectId(friend_id), "user_id": str(user["_id"])},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Update failed or no changes made.")
    
    return {"message": "✅ Friend profile updated."}


# ✅ Delete friend profile
async def delete_friend_profile(friend_id: str, user: dict):
    result = await friend_collection.delete_one({"_id": ObjectId(friend_id), "user_id": str(user["_id"])})

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
