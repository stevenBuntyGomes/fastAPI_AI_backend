# app/routes/lung_check.py

from fastapi import APIRouter, Depends, HTTPException
from ..schemas.lung_check_schema import LungCheckCreateRequest, LungCheckResponse
from ..models.lung_check_model import LungCheckModel
from ..utils.auth_utils import get_current_user
from ..db.mongo import lung_check_collection
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# ✅ Create or update the user's lung check history
@router.post("/lung-check", response_model=LungCheckResponse)
async def save_lung_check(
    data: LungCheckCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = str(current_user["_id"])

    # Update or insert lung check entry for the current user
    update_result = await lung_check_collection.update_one(
        {"user_id": user_id},
        {
            "$push": {
                "lung_check_history": {
                    "timestamp": data.timestamp,
                    "duration": data.duration
                }
            },
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    # Fetch updated record
    record = await lung_check_collection.find_one({"user_id": user_id})
    if not record:
        raise HTTPException(status_code=404, detail="Lung check record not found.")

    return LungCheckResponse(
        user_id=str(record["user_id"]),
        lung_check_history=record.get("lung_check_history", []),
        created_at=record.get("created_at", datetime.utcnow())
    )

# ✅ Get lung check history for the current user
@router.get("/lung-check", response_model=LungCheckResponse)
async def get_lung_check(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])

    record = await lung_check_collection.find_one({"user_id": user_id})
    if not record:
        raise HTTPException(status_code=404, detail="No lung check data found.")

    return LungCheckResponse(
        user_id=user_id,
        lung_check_history=record.get("lung_check_history", []),
        created_at=record.get("created_at", datetime.utcnow())
    )
