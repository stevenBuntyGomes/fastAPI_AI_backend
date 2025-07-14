from fastapi import HTTPException
from datetime import datetime
from bson import ObjectId

from ..db import lung_check_collection, users_collection
from ..models.lung_check_model import LungCheckModel
from ..schemas.lung_check_schema import LungCheckCreateRequest

# Create a new lung check entry for a user
async def create_lung_check(user, data: LungCheckCreateRequest):
    try:
        entry = data.dict()
        entry["user_id"] = str(user["_id"])
        entry["created_at"] = datetime.utcnow()

        result = await lung_check_collection.insert_one(entry)

        if result.inserted_id:
            return {"message": "✅ Lung check saved."}
        else:
            raise HTTPException(status_code=500, detail="❌ Failed to save lung check.")
    except Exception as e:
        print("❌ Error creating lung check:", e)
        raise HTTPException(status_code=500, detail=str(e))


# Fetch all lung checks for a user with user info
async def get_user_lung_checks(user):
    try:
        user_id = str(user["_id"])
        cursor = lung_check_collection.find({"user_id": user_id})
        results = []

        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc["user"] = {
                "id": str(user["_id"]),
                "email": user.get("email"),
                "name": user.get("name")
            }
            results.append(doc)

        return results
    except Exception as e:
        print("❌ Error fetching lung checks:", e)
        raise HTTPException(status_code=500, detail=str(e))
