from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime

from ..db.mongo import progress_collection, users_collection
from ..models.progress_model import ProgressModel
from ..schemas.progress_schema import ProgressCreateRequest, ProgressResponse
from ..models.auth import UserModel


# ✅ Save Progress (Create or Update)
async def save_user_progress(user_id: str, data: ProgressCreateRequest):
    existing = await progress_collection.find_one({"user_id": user_id})
    if existing:
        raise HTTPException(status_code=400, detail="❌ Progress already exists for this user.")

    update_data = {
        "user_id": user_id,
        "last_relapse_date": data.last_relapse_date,
        "quit_date": data.quit_date,
        "days_tracked": data.days_tracked or [],
        "milestones_unlocked": data.milestones_unlocked or [],
        "created_at": datetime.utcnow(),
    }

    await progress_collection.insert_one(update_data)
    return {"message": "✅ Progress created successfully."}

# ✅ Enhanced Progress Fetch with Milestone Calculation
from ..db.mongo import milestone_collection
from ..schemas.progress_schema import ProgressResponse, MilestoneStatus

async def get_user_progress(user_id: str) -> ProgressResponse:
    progress = await progress_collection.find_one({"user_id": user_id})
    if not progress:
        raise HTTPException(status_code=404, detail="❌ No progress found.")

    # ⏱ Calculate time since last relapse
    now = datetime.utcnow()
    relapse_time = progress.get("last_relapse_date") or progress["created_at"]
    minutes_since = (now - relapse_time).total_seconds() / 60

    # 🔐 Fetch milestone definitions
    milestone_docs = milestone_collection.find().sort("time_in_minutes", 1)
    milestones = [doc async for doc in milestone_docs]

    # 🎯 Process milestone status
    unlocked_names = set(progress.get("milestones_unlocked", []))
    latest_unlocked = None
    current_in_progress = None
    next_locked = None
    newly_unlocked = []

    for m in milestones:
        name = m["name"]
        if minutes_since >= m["time_in_minutes"]:
            if name not in unlocked_names:
                newly_unlocked.append(name)
            latest_unlocked = MilestoneStatus(
                name=name,
                description=m["description"],
                time_in_minutes=m["time_in_minutes"]
            )
        elif not current_in_progress:
            current_in_progress = MilestoneStatus(
                name=name,
                description=m["description"],
                time_in_minutes=m["time_in_minutes"],
                progress_percent=round((minutes_since / m["time_in_minutes"]) * 100, 2)
            )
        elif not next_locked:
            next_locked = MilestoneStatus(
                name=name,
                description=m["description"],
                time_in_minutes=m["time_in_minutes"]
            )
            break  # we only want 3 milestones max

    # ✍️ Update DB if new milestones unlocked
    if newly_unlocked:
        await progress_collection.update_one(
            {"_id": progress["_id"]},
            {"$addToSet": {"milestones_unlocked": {"$each": newly_unlocked}}}
        )
        unlocked_names.update(newly_unlocked)

    # ✅ Prepare response
    return ProgressResponse(
        user_id=str(progress["user_id"]),
        last_relapse_date=progress.get("last_relapse_date"),
        quit_date=progress.get("quit_date"),
        days_tracked=progress.get("days_tracked", []),
        milestones_unlocked=list(unlocked_names),
        created_at=progress.get("created_at", now),
        latest_unlocked=latest_unlocked,
        current_in_progress=current_in_progress,
        next_locked=next_locked,
        minutes_since_last_relapse=round(minutes_since, 2)
    )

# ✅ Reset Progress (User Failed)
async def reset_user_progress(user_id: str) -> ProgressResponse:
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found.")

    now = datetime.utcnow()

    # Fetch current progress (to preserve milestones + created_at)
    existing_progress = await progress_collection.find_one({"user_id": user_id})
    if not existing_progress:
        raise HTTPException(status_code=404, detail="❌ No progress data to reset.")

    milestones = existing_progress.get("milestones_unlocked", [])
    created_at = existing_progress.get("created_at", now)

    # Reset progress fields (but NOT created_at)
    reset_data = {
        "last_relapse_date": now,
        "quit_date": now,
        "days_tracked": [],
        "milestones_unlocked": milestones,
    }

    await progress_collection.update_one(
        {"user_id": user_id},
        {"$set": reset_data}
    )

    # Reuse your main progress display logic
    from .progress_controller import get_user_progress
    return await get_user_progress(user_id)