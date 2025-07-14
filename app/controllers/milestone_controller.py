from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from ..db.mongo import milestone_collection, users_collection
from ..models.milestone_model import MilestoneModel
from ..schemas.milestone_schema import MilestoneCreateRequest, MilestoneResponse

# ✅ Save or Update Milestone Progress
async def create_or_update_milestone(user: dict, data: MilestoneCreateRequest) -> MilestoneResponse:
    user_id = user["_id"]

    update_data = {
        "user_id": user_id,
        "last_relapse_date": data.last_relapse_date,
        "milestones_unlocked": data.milestones_unlocked,
        "updated_at": datetime.utcnow()
    }

    await milestone_collection.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )

    # Fetch updated document
    doc = await milestone_collection.find_one({"user_id": user_id})
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to save milestone data.")

    return await serialize_milestone_with_user(doc)

# ✅ Get Milestone Progress for Authenticated User
async def get_user_milestone(user: dict) -> MilestoneResponse:
    user_id = user["_id"]
    doc = await milestone_collection.find_one({"user_id": user_id})

    if not doc:
        raise HTTPException(status_code=404, detail="Milestone data not found.")

    return await serialize_milestone_with_user(doc)

# ✅ Attach user details to response
async def serialize_milestone_with_user(doc: dict) -> MilestoneResponse:
    user = await users_collection.find_one({"_id": doc["user_id"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    return MilestoneResponse(
        last_relapse_date=doc.get("last_relapse_date"),
        milestones_unlocked=doc.get("milestones_unlocked", []),
        user={
            "id": str(user["_id"]),
            "email": user.get("email"),
            "name": user.get("name")
        }
    )
