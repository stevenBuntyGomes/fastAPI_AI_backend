# app/controllers/recovery_controller.py

from datetime import datetime, timedelta
from fastapi import HTTPException

from ..schemas.recovery_schema import RecoveryCreateRequest, RecoveryResponse
from ..db.mongo import recovery_collection
from ..models.auth import UserModel  # Uses your existing UserModel

from bson import ObjectId


# 🎯 Helper to calculate recovery percentage and quit_date
def calculate_recovery_data(last_relapse_date: datetime):
    today = datetime.utcnow()
    days_passed = (today - last_relapse_date).days
    percentage = min((days_passed / 90) * 100, 100)
    quit_date = last_relapse_date + timedelta(days=90)
    return round(percentage, 2), quit_date


# 🚀 Create recovery data
async def create_recovery(current_user: dict, data: RecoveryCreateRequest) -> RecoveryResponse:
    user_id = str(current_user["_id"])

    existing = await recovery_collection.find_one({"user_id": user_id})
    if existing:
        raise HTTPException(status_code=400, detail="Recovery data already exists.")

    recovery_percentage, quit_date = calculate_recovery_data(data.last_relapse_date)

    record = {
        "user_id": user_id,
        "last_relapse_date": data.last_relapse_date,
        "recovery_percentage": recovery_percentage,
        "quit_date": quit_date,
        "created_at": datetime.utcnow()
    }

    await recovery_collection.insert_one(record)

    return RecoveryResponse(
        last_relapse_date=data.last_relapse_date,
        quit_date=quit_date,
        recovery_percentage=recovery_percentage,
        user=current_user  # dict
    )


# 🔍 Get recovery data by user
async def get_recovery_by_user(current_user: dict) -> RecoveryResponse:
    user_id = str(current_user["_id"])

    record = await recovery_collection.find_one({"user_id": user_id})
    if not record:
        raise HTTPException(status_code=404, detail="Recovery data not found.")

    return RecoveryResponse(
        last_relapse_date=record["last_relapse_date"],
        quit_date=record["quit_date"],
        recovery_percentage=record["recovery_percentage"],
        user=current_user  # dict
    )


# 🔁 Update recovery data
async def update_recovery(current_user: dict, data: RecoveryCreateRequest) -> RecoveryResponse:
    user_id = str(current_user["_id"])

    recovery_percentage, quit_date = calculate_recovery_data(data.last_relapse_date)

    updated = await recovery_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "last_relapse_date": data.last_relapse_date,
                "quit_date": quit_date,
                "recovery_percentage": recovery_percentage,
                "updated_at": datetime.utcnow()
            }
        }
    )

    if updated.modified_count == 0:
        raise HTTPException(status_code=404, detail="Recovery data not found or not modified.")

    return RecoveryResponse(
        last_relapse_date=data.last_relapse_date,
        quit_date=quit_date,
        recovery_percentage=recovery_percentage,
        user=current_user  # dict
    )
