# app/controllers/lung_relining_controller.py

from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId
from app.schemas.lung_relining_schema import (
    LungReliningCreateRequest,
    LungReliningResponse,
)
from app.models.lung_relining_model import LungReliningModel
from app.db import lung_relining_collection, users_collection


# Create a new lung relining entry for the authenticated user
async def create_lung_relining_entry(data: LungReliningCreateRequest, user: dict):
    entry = LungReliningModel(
        user_id=str(user["_id"]),
        last_relapse_date=data.last_relapse_date,
        created_at=datetime.utcnow()
    )

    # Insert into DB
    await lung_relining_collection.insert_one(entry.model_dump(by_alias=True))

    # Add user info to response
    entry_dict = entry.model_dump()
    entry_dict["user"] = {
        "id": str(user["_id"]),
        "email": user.get("email"),
        "name": user.get("name")
    }

    return LungReliningResponse(**entry_dict)


# Fetch all lung relining entries for the authenticated user
async def get_user_lung_relining_entries(user: dict):
    user_id = str(user["_id"])
    cursor = lung_relining_collection.find({"user_id": user_id}).sort("created_at", -1)
    entries = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        doc["user"] = {
            "id": str(user["_id"]),
            "email": user.get("email"),
            "name": user.get("name")
        }
        entries.append(LungReliningResponse(**doc))

    return entries
