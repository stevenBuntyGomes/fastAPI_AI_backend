# app/controllers/progress_controller.py
from typing import Optional, List
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime

from ..db.mongo import progress_collection, users_collection, milestone_collection
from ..schemas.progress_schema import (
    ProgressCreateRequest,
    ProgressResponse,
    MilestoneStatus,
)

# ── config ──────────────────────────────────────────────────────────────────────
AURA_PER_MILESTONE = 20  # ← award per newly unlocked milestone

def _as_oid(user_id: str) -> ObjectId:
    try:
        return ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id")

async def _increment_user_aura(user_id: str, points: int) -> None:
    """
    Safely increment a user's aura by `points` (positive int). No-op if points <= 0.
    """
    if points <= 0:
        return
    await users_collection.update_one(
        {"_id": _as_oid(user_id)},
        {"$inc": {"aura": points}, "$set": {"updated_at": datetime.utcnow()}}
    )

# ✅ Save Progress (Create or Update)
async def save_user_progress(user_id: str, data: ProgressCreateRequest):
    existing = await progress_collection.find_one({"user_id": user_id})

    last_relapse = data.last_relapse_date
    # If schema has quit_date, use it; else default to last_relapse
    quit_date = getattr(data, "quit_date", None) or last_relapse

    # Normalize incoming milestones list (de-dupe, keep order)
    incoming_unlocked: List[str] = list(dict.fromkeys(data.milestones_unlocked or []))

    if existing:
        # Determine which milestones are *newly added* compared to what's already stored
        previously_unlocked = set(existing.get("milestones_unlocked", []))
        newly_added = [m for m in incoming_unlocked if m not in previously_unlocked]

        # Update in place
        await progress_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "last_relapse_date": last_relapse,
                "quit_date": quit_date,
                "days_tracked": data.days_tracked or [],
                "milestones_unlocked": incoming_unlocked,
                "updated_at": datetime.utcnow(),
            }}
        )

        # ⭐ Aura: +20 per newly added milestone (only when values are added)
        if newly_added:
            await _increment_user_aura(user_id, AURA_PER_MILESTONE * len(newly_added))

        return {"message": "✅ Progress updated successfully."}

    else:
        # Create new (no aura increment here; nothing was "added" versus prior state)
        doc = {
            "user_id": user_id,
            "last_relapse_date": last_relapse,
            "quit_date": quit_date,
            "days_tracked": data.days_tracked or [],
            "milestones_unlocked": incoming_unlocked,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        await progress_collection.insert_one(doc)
        return {"message": "✅ Progress created successfully."}

# ✅ Enhanced Progress Fetch with Milestone Calculation
async def get_user_progress(user_id: str) -> ProgressResponse:
    progress = await progress_collection.find_one({"user_id": user_id})
    if not progress:
        raise HTTPException(status_code=404, detail="❌ No progress found.")

    # ⏱ Calculate time since last relapse (naive UTC as before)
    now = datetime.utcnow()
    relapse_time = progress.get("last_relapse_date") or progress["created_at"]
    minutes_since = (now - relapse_time).total_seconds() / 60

    # 🔐 Fetch milestone definitions
    milestone_docs = milestone_collection.find().sort("time_in_minutes", 1)
    milestones = [doc async for doc in milestone_docs]

    # 🎯 Process milestone status
    unlocked_names = set(progress.get("milestones_unlocked", []))
    latest_unlocked: Optional[MilestoneStatus] = None
    current_in_progress: Optional[MilestoneStatus] = None
    next_locked: Optional[MilestoneStatus] = None
    newly_unlocked: List[str] = []

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
        # Add unique new names to the set in DB
        await progress_collection.update_one(
            {"_id": progress["_id"]},
            {"$addToSet": {"milestones_unlocked": {"$each": newly_unlocked}}}
        )
        # ⭐ Aura: +20 per *actually* newly unlocked milestone
        await _increment_user_aura(user_id, AURA_PER_MILESTONE * len(newly_unlocked))
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
    # Ensure user exists
    _ = await users_collection.find_one({"_id": _as_oid(user_id)})
    if not _:
        raise HTTPException(status_code=404, detail="❌ User not found.")

    now = datetime.utcnow()

    # Fetch current progress (to preserve milestones + created_at)
    existing_progress = await progress_collection.find_one({"user_id": user_id})
    if not existing_progress:
        raise HTTPException(status_code=404, detail="❌ No progress data to reset.")

    milestones = existing_progress.get("milestones_unlocked", [])
    created_at = existing_progress.get("created_at", now)

    # Reset progress fields (but NOT created_at, and no aura changes here)
    reset_data = {
        "last_relapse_date": now,
        "quit_date": now,
        "days_tracked": [],
        "milestones_unlocked": milestones,
        "created_at": created_at,  # keep original created_at
        "updated_at": now,
    }

    await progress_collection.update_one(
        {"user_id": user_id},
        {"$set": reset_data}
    )

    # Return fresh computed view
    return await get_user_progress(user_id)
