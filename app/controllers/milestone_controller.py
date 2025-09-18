# app/controllers/milestone_controller.py
from datetime import datetime
from typing import List, Dict
from bson import ObjectId
from pymongo import UpdateOne
from fastapi import HTTPException

from ..db.mongo import milestone_collection
# Optional: if you have utcnow helper already, import and use it
try:
    from ..utils.datetime_utils import utcnow  # tz-aware, no milliseconds (if you added earlier)
except Exception:
    from datetime import datetime as _dt
    def utcnow():
        return _dt.utcnow()  # fallback (naive); fine for seeding

def _to_minutes(*, minutes=0, hours=0, days=0, weeks=0, months=0, years=0) -> int:
    """Convert mixed units to minutes. months=30 days, year=365 days."""
    MIN_PER_HOUR = 60
    MIN_PER_DAY = 24 * 60                     # 1440
    MIN_PER_WEEK = 7 * MIN_PER_DAY           # 10080
    MIN_PER_MONTH = 30 * MIN_PER_DAY         # 43200
    MIN_PER_YEAR = 365 * MIN_PER_DAY         # 525600
    total = 0
    total += minutes
    total += hours * MIN_PER_HOUR
    total += days * MIN_PER_DAY
    total += weeks * MIN_PER_WEEK
    total += months * MIN_PER_MONTH
    total += years * MIN_PER_YEAR
    return int(total)

# Canonical list (names + descriptions from your message)
_SEED: List[Dict] = [
    {
        "name": "Heart Reset",
        "description": "Your heart rate and blood pressure start dropping towards normal levels.",
        "time_in_minutes": _to_minutes(minutes=20),
    },
    {
        "name": "Craving Spike",
        "description": "First cravings hit, but every hour without vaping builds your control.",
        "time_in_minutes": _to_minutes(hours=2),
    },
    {
        "name": "Blood Flow Boost",
        "description": "Circulation improves, oxygen starts flowing better throughout your body.",
        "time_in_minutes": _to_minutes(hours=10),
    },
    {
        "name": "Breakthrough Mark",
        "description": "Nicotine starts leaving your system, cravings peak but you’re stronger.",
        "time_in_minutes": _to_minutes(hours=24),
    },
    {
        "name": "Body Reboot",
        "description": "Breathing, taste, and smell begin noticeably improving, first real health shift.",
        "time_in_minutes": _to_minutes(days=3),
    },
    {
        "name": "Cravings Crash",
        "description": "Major cravings fade significantly, you’re through the hardest mental barrier.",
        "time_in_minutes": _to_minutes(days=7),
    },
    {
        "name": "Clear Head Zone",
        "description": "Mood, focus, and mental sharpness noticeably bounce back.",
        "time_in_minutes": _to_minutes(weeks=2),
    },
    {
        "name": "Energy Return",
        "description": "Energy levels improve, breathing feels easier, stamina starts coming back.",
        "time_in_minutes": _to_minutes(months=1),
    },
    {
        "name": "Willpower Badge",
        "description": "You’ve resisted cravings for two months—discipline is locked in.",
        "time_in_minutes": _to_minutes(months=2),
    },
    {
        "name": "Nicotine-Free Badge",
        "description": "Body is nicotine-free, lung repair and deeper healing are well underway.",
        "time_in_minutes": _to_minutes(months=3),
    },
    {
        "name": "Lung Vitality Rise",
        "description": "Lung function noticeably improves, your breathing feels smoother and stronger.",
        "time_in_minutes": _to_minutes(months=4),
    },
    {
        "name": "Respiratory Renewal",
        "description": "Breathing is easier, lungs feel stronger with reduced inflammation.",
        "time_in_minutes": _to_minutes(months=5),
    },
    {
        "name": "Lung Repair Phase",
        "description": "Lung function improves dramatically—you’re reversing real damage now.",
        "time_in_minutes": _to_minutes(months=6),
    },
    {
        "name": "Airway Strength Badge",
        "description": "Airways are stronger, overall lung health approaches a non-vaper’s baseline.",
        "time_in_minutes": _to_minutes(months=9),
    },
    {
        "name": "GOAT",
        "description": "Your heart and lung health show major recovery, relapse risk drops significantly.",
        "time_in_minutes": _to_minutes(years=1),
    },
]

async def seed_milestones() -> dict:
    """
    Idempotent upsert of milestones by 'name'.
    - Creates a unique index on 'name' if not present.
    - Sets/updates description and time_in_minutes.
    - Sets created_at on first insert.
    """
    # Ensure unique index
    try:
        await milestone_collection.create_index("name", unique=True)
    except Exception:
        pass  # ignore if already exists

    ops = []
    now = utcnow()
    for m in _SEED:
        ops.append(
            UpdateOne(
                {"name": m["name"]},
                {
                    "$set": {
                        "description": m["description"],
                        "time_in_minutes": int(m["time_in_minutes"]),
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        )

    if not ops:
        return {"matched": 0, "modified": 0, "upserted": 0}

    bulk_result = await milestone_collection.bulk_write(ops, ordered=False)
    # Normalize counts across PyMongo/Motor versions
    matched = getattr(bulk_result, "matched_count", 0)
    modified = getattr(bulk_result, "modified_count", 0)
    upserted = len(getattr(bulk_result, "upserted_ids", {}) or {})

    return {
        "message": "Milestones seeded.",
        "matched": matched,
        "modified": modified,
        "upserted": upserted,
        "total": len(_SEED),
    }

async def list_milestones() -> List[dict]:
    cursor = milestone_collection.find().sort("time_in_minutes", 1)
    res: List[dict] = []
    async for doc in cursor:
        doc["id"] = str(doc.get("_id"))
        doc.pop("_id", None)
        # keep only the public fields
        res.append({
            "id": doc["id"],
            "name": doc["name"],
            "description": doc["description"],
            "time_in_minutes": int(doc["time_in_minutes"]),
            "created_at": doc.get("created_at"),
        })
    return res
