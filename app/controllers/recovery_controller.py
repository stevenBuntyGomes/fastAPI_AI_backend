from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from ..schemas.recovery_schema import RecoveryCreateRequest, RecoveryResponse, UserPreview
from ..db.mongo import recovery_collection
from ..models.auth import UserModel  # Optional, not used directly


# 🎯 Helper to calculate recovery % and quit date
def calculate_recovery_data(last_relapse_date: datetime):
    today = datetime.now(timezone.utc)
    days_passed = (today - last_relapse_date).days
    percentage = min((days_passed / 90) * 100, 100)
    quit_date = last_relapse_date + timedelta(days=90)
    return round(percentage, 2), quit_date


# 🔄 Helper to convert user dict to UserPreview
def get_user_preview(current_user: dict) -> UserPreview:
    return UserPreview(
        id=str(current_user["_id"]),
        email=current_user["email"],
        name=current_user.get("name")
    )


# 🚀 Create new recovery entry
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
        "created_at": datetime.now(timezone.utc)
    }

    await recovery_collection.insert_one(record)

    return RecoveryResponse(
        last_relapse_date=data.last_relapse_date,
        quit_date=quit_date,
        recovery_percentage=recovery_percentage,
        user=get_user_preview(current_user)
    )


# 🔍 Get recovery data for current user
async def get_recovery_by_user(current_user: dict) -> RecoveryResponse:
    user_id = str(current_user["_id"])

    record = await recovery_collection.find_one({"user_id": user_id})
    if not record:
        raise HTTPException(status_code=404, detail="Recovery data not found.")

    return RecoveryResponse(
        last_relapse_date=record["last_relapse_date"],
        quit_date=record["quit_date"],
        recovery_percentage=record["recovery_percentage"],
        user=get_user_preview(current_user)
    )


# 🔁 Update recovery entry
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
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Recovery data not found.")

    return RecoveryResponse(
        last_relapse_date=data.last_relapse_date,
        quit_date=quit_date,
        recovery_percentage=recovery_percentage,
        user=get_user_preview(current_user)
    )
