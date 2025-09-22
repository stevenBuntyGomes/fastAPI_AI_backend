from datetime import datetime, timezone
from fastapi import HTTPException
from app.schemas.lung_relining_schema import (
    LungReliningCreateRequest,
    LungReliningResponse,
)
from app.models.lung_relining_model import LungReliningModel
from app.db import lung_relining_collection

NINETY_DAYS_SECONDS = 90 * 24 * 60 * 60  # 7,776,000

def _ensure_utc(dt: datetime) -> datetime:
    """
    Treat naive datetimes as UTC; convert aware datetimes to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# Create a new lung relining entry for the authenticated user
async def create_lung_relining_entry(data: LungReliningCreateRequest, user: dict):
    try:
        last_dt_utc = _ensure_utc(data.last_relapse_date)
        quit_dt_utc = _ensure_utc(data.quit_date)

        # Compute (last_relapse_date - quit_date) in seconds (float)
        delta_seconds = (last_dt_utc - quit_dt_utc).total_seconds()

        # Percentage of 90 days
        percent_of_90_days = (delta_seconds / NINETY_DAYS_SECONDS) * 100

        entry = LungReliningModel(
            user_id=str(user["_id"]),
            last_relapse_date=last_dt_utc,
            quit_date=quit_dt_utc,
            delta_seconds=delta_seconds,
            percent_of_90_days=percent_of_90_days,
            created_at=datetime.utcnow(),
        )

        # Insert into DB
        result = await lung_relining_collection.insert_one(entry.model_dump(by_alias=True))
        entry_id = str(result.inserted_id)

        # Build response
        resp = LungReliningResponse(
            id=entry_id,
            last_relapse_date=entry.last_relapse_date,
            quit_date=entry.quit_date,
            delta_seconds=entry.delta_seconds,
            percent_of_90_days=entry.percent_of_90_days,
            created_at=entry.created_at,
            user={
                "id": str(user["_id"]),
                "email": user.get("email"),
                "name": user.get("name"),
            },
        )
        return resp

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create lung relining entry: {e}")

# Fetch all lung relining entries for the authenticated user
async def get_user_lung_relining_entries(user: dict):
    try:
        user_id = str(user["_id"])
        cursor = lung_relining_collection.find({"user_id": user_id}).sort("created_at", -1)
        entries = []
        async for doc in cursor:
            # Normalize id
            doc["id"] = str(doc.get("_id") or doc.get("id"))
            # Ensure required fields exist; if stored older records lack new fields, compute defensively
            last_dt = doc.get("last_relapse_date")
            quit_dt = doc.get("quit_date")

            # Backfill if needed
            if "delta_seconds" not in doc or "percent_of_90_days" not in doc:
                if last_dt and quit_dt:
                    last_dt_utc = _ensure_utc(last_dt)
                    quit_dt_utc = _ensure_utc(quit_dt)
                    delta_seconds = (last_dt_utc - quit_dt_utc).total_seconds()
                    percent_of_90_days = (delta_seconds / NINETY_DAYS_SECONDS) * 100
                    doc["delta_seconds"] = delta_seconds
                    doc["percent_of_90_days"] = percent_of_90_days
                else:
                    doc["delta_seconds"] = 0.0
                    doc["percent_of_90_days"] = 0.0

            doc["user"] = {
                "id": str(user["_id"]),
                "email": user.get("email"),
                "name": user.get("name"),
            }

            entries.append(LungReliningResponse(**{
                "id": doc["id"],
                "last_relapse_date": doc["last_relapse_date"],
                "quit_date": doc["quit_date"],
                "delta_seconds": float(doc["delta_seconds"]),
                "percent_of_90_days": float(doc["percent_of_90_days"]),
                "created_at": doc["created_at"],
                "user": doc["user"],
            }))

        return entries

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch lung relining entries: {e}")
