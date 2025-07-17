from fastapi import APIRouter, Depends, HTTPException
from ..schemas.lung_check_schema import LungCheckCreateRequest, LungCheckResponse
from ..utils.auth_utils import get_current_user
from ..db.mongo import lung_check_collection
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# ✅ Create or update the user's lung check history (bulk insert)
@router.post("/lung-check", response_model=LungCheckResponse)
async def save_lung_check(
    data: LungCheckCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = str(current_user["_id"])

    if not data.lung_check_history:
        raise HTTPException(status_code=400, detail="No lung check data provided.")

    # Prepare list of entries
    entries = [
        {
            "timestamp": entry.timestamp,
            "duration": entry.duration
        }
        for entry in data.lung_check_history
    ]

    # Upsert user's lung check document and push new entries
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

    # Return updated record
    record = await lung_check_collection.find_one({"user_id": user_id})
    if not record:
        raise HTTPException(status_code=404, detail="Lung check record not found.")

    return {
        "_id": str(record["_id"]),
        "user_id": str(record["user_id"]),
        "lung_check_history": record.get("lung_check_history", []),
        "created_at": record.get("created_at", datetime.utcnow())
    }


# ✅ Get lung check history for the current user
@router.get("/lung-check", response_model=LungCheckResponse)
async def get_lung_check(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])

    record = await lung_check_collection.find_one({"user_id": user_id})
    if not record:
        raise HTTPException(status_code=404, detail="No lung check data found.")

    return {
        "_id": str(record["_id"]),
        "user_id": user_id,
        "lung_check_history": record.get("lung_check_history", []),
        "created_at": record.get("created_at", datetime.utcnow())
    }
