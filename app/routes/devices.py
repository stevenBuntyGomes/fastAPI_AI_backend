from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.post("/apns")
async def register_apns_device(body: dict):
    # Just take whatever comes in and store it
    doc = {
        **body,
        "platform": "ios",
        "updated_at": datetime.utcnow(),
    }

    # Upsert by (user_id, platform, environment) if those exist
    query = {
        "user_id": body.get("user_id"),
        "platform": "ios",
        "environment": body.get("environment")
    }

    result = await devices_collection.update_one(
        query,
        {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )

    return {
        "ok": True,
        "matched": result.matched_count,
        "upserted": bool(result.upserted_id),
    }