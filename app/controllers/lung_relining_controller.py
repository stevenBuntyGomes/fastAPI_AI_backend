from datetime import datetime, timezone
from fastapi import HTTPException, status
from bson import ObjectId
from app.schemas.lung_relining_schema import (
    LungReliningCreateRequest,
    LungReliningUpdateRequest,
    LungReliningResponse,
)
from app.models.lung_relining_model import LungReliningModel
from app.db import lung_relining_collection  # assumes Motor collection is exported here

NINETY_DAYS_SECONDS = 90 * 24 * 60 * 60  # 7,776,000

def _ensure_utc(dt):
    """Treat naive datetimes as UTC; convert aware datetimes to UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def _compute_metrics(last_dt_utc, quit_dt_utc):
    """Return (delta_seconds, percent_of_90_days)."""
    delta_seconds = (last_dt_utc - quit_dt_utc).total_seconds()
    percent = (delta_seconds / NINETY_DAYS_SECONDS) * 100
    return float(delta_seconds), float(percent)

async def create_lung_relining_entry(data: LungReliningCreateRequest, user: dict):
    """
    Create a new lung_relining entry for the authenticated user.
    Auto-generates ObjectId; computes metrics; returns created doc (with id).
    """
    try:
        last_dt_utc = _ensure_utc(data.last_relapse_date)
        quit_dt_utc = _ensure_utc(data.quit_date)

        delta_seconds, percent = _compute_metrics(last_dt_utc, quit_dt_utc)

        entry = LungReliningModel(
            user_id=str(user["_id"]),
            last_relapse_date=last_dt_utc,
            quit_date=quit_dt_utc,
            delta_seconds=delta_seconds,
            percent_of_90_days=percent,
            created_at=datetime.utcnow(),
            updated_at=None,
        )

        # IMPORTANT: don't send "_id": None
        doc = entry.model_dump(by_alias=True, exclude_none=True, exclude={"id"})
        result = await lung_relining_collection.insert_one(doc)
        entry_id = str(result.inserted_id)

        return LungReliningResponse(
            id=entry_id,
            last_relapse_date=entry.last_relapse_date,
            quit_date=entry.quit_date,
            delta_seconds=entry.delta_seconds,
            percent_of_90_days=entry.percent_of_90_days,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            user={"id": str(user["_id"]), "email": user.get("email"), "name": user.get("name")},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create lung relining entry: {e}")

async def get_user_lung_relining_entries(user: dict):
    """
    Return all entries for the current user (latest first).
    """
    try:
        user_id = str(user["_id"])
        cursor = lung_relining_collection.find({"user_id": user_id}).sort("created_at", -1)
        entries = []
        async for doc in cursor:
            entries.append(LungReliningResponse(
                id=str(doc["_id"]),
                last_relapse_date=doc["last_relapse_date"],
                quit_date=doc["quit_date"],
                delta_seconds=float(doc.get("delta_seconds", 0.0)),
                percent_of_90_days=float(doc.get("percent_of_90_days", 0.0)),
                created_at=doc["created_at"],
                updated_at=doc.get("updated_at"),
                user={"id": user_id, "email": user.get("email"), "name": user.get("name")},
            ))
        return entries
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch lung relining entries: {e}")

async def get_lung_relining_entry_by_id(entry_id: str, user: dict):
    """
    Fetch a single entry by its ObjectId; must belong to current user.
    """
    try:
        oid = ObjectId(entry_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entry_id")

    doc = await lung_relining_collection.find_one({"_id": oid, "user_id": str(user["_id"])})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    return LungReliningResponse(
        id=str(doc["_id"]),
        last_relapse_date=doc["last_relapse_date"],
        quit_date=doc["quit_date"],
        delta_seconds=float(doc.get("delta_seconds", 0.0)),
        percent_of_90_days=float(doc.get("percent_of_90_days", 0.0)),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at"),
        user={"id": str(user["_id"]), "email": user.get("email"), "name": user.get("name")},
    )

async def update_lung_relining_last_relapse(entry_id: str, data: LungReliningUpdateRequest, user: dict):
    """
    Update only last_relapse_date by _id (must belong to user), then
    recompute delta_seconds and percent_of_90_days using the stored quit_date.
    Returns the updated document.
    """
    # Validate ObjectId
    try:
        oid = ObjectId(entry_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entry_id")

    # Fetch doc with ownership enforcement
    doc = await lung_relining_collection.find_one({"_id": oid, "user_id": str(user["_id"])})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    stored_quit = doc.get("quit_date")
    if not stored_quit:
        raise HTTPException(status_code=400, detail="Cannot update: stored quit_date is missing")

    # Normalize to UTC
    new_last_utc = _ensure_utc(data.last_relapse_date)
    quit_dt_utc  = _ensure_utc(stored_quit)

    # Recompute metrics (SAME calculation as create)
    delta_seconds, percent = _compute_metrics(new_last_utc, quit_dt_utc)

    update_doc = {
        "last_relapse_date": new_last_utc,
        "delta_seconds": float(delta_seconds),
        "percent_of_90_days": float(percent),
        "updated_at": datetime.utcnow(),
    }

    await lung_relining_collection.update_one(
        {"_id": oid, "user_id": str(user["_id"])},
        {"$set": update_doc},
    )

    # Return updated doc with same _id
    updated = await lung_relining_collection.find_one({"_id": oid})
    return LungReliningResponse(
        id=str(updated["_id"]),
        last_relapse_date=updated["last_relapse_date"],
        quit_date=updated["quit_date"],
        delta_seconds=float(updated.get("delta_seconds", 0.0)),
        percent_of_90_days=float(updated.get("percent_of_90_days", 0.0)),
        created_at=updated["created_at"],
        updated_at=updated.get("updated_at"),
        user={"id": str(user["_id"]), "email": user.get("email"), "name": user.get("name")},
    )
