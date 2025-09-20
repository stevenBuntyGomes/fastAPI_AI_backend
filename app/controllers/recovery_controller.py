from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from ..schemas.recovery_schema import RecoveryCreateRequest, RecoveryResponse, UserPreview
from ..db.mongo import recovery_collection
from ..models.auth import UserModel  # Optional, not used directly


# ── helpers: UTC-safe ───────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def to_utc_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# 🎯 Helper to calculate recovery % from a baseline date (quit_date or last_relapse)
# NOTE: keep signature/return-count compatible with your existing calls
def calculate_recovery_data(baseline_date: datetime):
    baseline = to_utc_aware(baseline_date)
    today = now_utc()
    days_passed = (today - baseline).days
    percentage = min(max((days_passed / 90) * 100, 0), 100)  # clamp 0..100
    quit_date = baseline  # <-- NO forcing +90 anymore; quit_date = baseline user intent
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

    # baseline = quit_date (if provided in schema), else last_relapse_date
    baseline = to_utc_aware(getattr(data, "quit_date", None)) or to_utc_aware(data.last_relapse_date)

    recovery_percentage, quit_date = calculate_recovery_data(baseline)

    record = {
        "user_id": user_id,
        "last_relapse_date": to_utc_aware(data.last_relapse_date),
        "recovery_percentage": recovery_percentage,
        "quit_date": quit_date,            # <-- baseline, not +90
        "created_at": now_utc()
    }

    await recovery_collection.insert_one(record)

    return RecoveryResponse(
        last_relapse_date=record["last_relapse_date"],
        quit_date=record["quit_date"],
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
        last_relapse_date=to_utc_aware(record["last_relapse_date"]),
        quit_date=to_utc_aware(record["quit_date"]),
        recovery_percentage=record["recovery_percentage"],
        user=get_user_preview(current_user)
    )


# 🔁 Update recovery entry
async def update_recovery(current_user: dict, data: RecoveryCreateRequest) -> RecoveryResponse:
    user_id = str(current_user["_id"])

    # baseline = quit_date (if provided), else last_relapse_date
    baseline = to_utc_aware(getattr(data, "quit_date", None)) or to_utc_aware(data.last_relapse_date)
    recovery_percentage, quit_date = calculate_recovery_data(baseline)

    updated = await recovery_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "last_relapse_date": to_utc_aware(data.last_relapse_date),
                "quit_date": quit_date,                # <-- baseline, not +90
                "recovery_percentage": recovery_percentage,
                "updated_at": now_utc()
            }
        }
    )

    if updated.matched_count == 0:
        raise HTTPException(status_code=404, detail="Recovery data not found.")

    return RecoveryResponse(
        last_relapse_date=to_utc_aware(data.last_relapse_date),
        quit_date=quit_date,
        recovery_percentage=recovery_percentage,
        user=get_user_preview(current_user)
    )
