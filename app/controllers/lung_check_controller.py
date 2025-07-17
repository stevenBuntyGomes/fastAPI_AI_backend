from fastapi import HTTPException
from datetime import datetime
from bson import ObjectId

from ..db import lung_check_collection, users_collection
from ..models.lung_check_model import LungCheckModel
from ..schemas.lung_check_schema import LungCheckCreateRequest

# Create a new lung check entry for a user
async def create_lung_check(user, data: LungCheckCreateRequest):
    try:
        user_id = str(user["_id"])

        if not data.lung_check_history:
            raise HTTPException(status_code=400, detail="No lung check data provided.")

        # Prepare entries for $push
        entries = [
            {
                "timestamp": entry.timestamp,
                "duration": entry.duration
            }
            for entry in data.lung_check_history
        ]

        # Push to existing document or insert if not present
        await lung_check_collection.update_one(
            {"user_id": user_id},
            {
                "$push": {"lung_check_history": {"$each": entries}},
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        return {"message": "✅ Lung check(s) saved successfully."}

    except Exception as e:
        print("❌ Error creating lung check:", e)
        raise HTTPException(status_code=500, detail="Failed to save lung check history.")

# Fetch all lung checks for a user with user info
async def get_user_lung_checks(user):
    try:
        user_id = str(user["_id"])
        doc = await lung_check_collection.find_one({"user_id": user_id})

        if not doc:
            raise HTTPException(status_code=404, detail="No lung check data found.")

        doc["id"] = str(doc["_id"])
        doc["user"] = {
            "id": str(user["_id"]),
            "email": user.get("email"),
            "name": user.get("name")
        }

        return doc

    except Exception as e:
        print("❌ Error fetching lung check:", e)
        raise HTTPException(status_code=500, detail=str(e))