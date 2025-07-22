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
from fastapi import HTTPException
from datetime import datetime
from bson import ObjectId

from ..db import lung_check_collection, users_collection
from ..models.lung_check_model import LungCheckModel

# 🧠 Scrollable Lung Check Fetch
async def get_user_lung_checks(user, skip: int = 0, limit: int = 7):
    try:
        user_id = str(user["_id"])

        doc = await lung_check_collection.find_one({"user_id": user_id})
        if not doc or "lung_check_history" not in doc:
            raise HTTPException(status_code=404, detail="No lung check history found.")

        all_entries = doc["lung_check_history"]

        # Sort entries by timestamp descending
        sorted_entries = sorted(all_entries, key=lambda x: x["timestamp"], reverse=True)

        # Apply pagination
        paginated_entries = sorted_entries[skip:skip + limit]

        return {
            "user": {
                "id": str(user["_id"]),
                "name": user.get("name"),
                "email": user.get("email")
            },
            "count": len(all_entries),
            "skip": skip,
            "limit": limit,
            "lung_check_history": paginated_entries
        }

    except Exception as e:
        print("❌ Error fetching lung check history:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch lung check data.")
