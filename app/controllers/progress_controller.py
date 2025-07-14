from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime

from ..db.mongo import progress_collection, users_collection
from ..models.progress_model import ProgressModel
from ..schemas.progress_schema import ProgressCreateRequest, ProgressResponse, LungCheckEntry
from ..models.auth import UserModel


# ✅ Save Progress (Create or Update)
async def save_user_progress(user_id: str, data: ProgressCreateRequest):
    # Upsert progress entry for this user
    update_data = {
        "user_id": user_id,
        "last_relapse_date": data.last_relapse_date,
        "quit_date": data.quit_date,
        "days_tracked": data.days_tracked or [],
        "lung_check_history": [entry.dict() for entry in data.lung_check_history] if data.lung_check_history else [],
        "milestones_unlocked": data.milestones_unlocked or [],
        "created_at": datetime.utcnow(),
    }

    await progress_collection.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )
    return {"message": "✅ Progress saved successfully."}


# ✅ Fetch Progress with Populated User Info
async def get_user_progress(user_id: str):
    progress = await progress_collection.find_one({"user_id": user_id})
    if not progress:
        raise HTTPException(status_code=404, detail="❌ No progress found.")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found.")

    # Clean up and format response
    progress["_id"] = str(progress["_id"])
    progress["user_id"] = str(progress["user_id"])
    user["_id"] = str(user["_id"])

    return {
        "progress": progress,
        "user": {
            "id": user["_id"],
            "name": user.get("name"),
            "email": user.get("email")
        }
    }
