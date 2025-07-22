# app/controllers/milestone_controller.py

from datetime import datetime
from fastapi import HTTPException
from typing import List

from ..db.mongo import milestone_collection
from ..schemas.milestone_schema import MilestoneSchema

# ✅ Get all static milestones (sorted by time)
async def get_all_milestones() -> List[MilestoneSchema]:
    milestones = []
    async for doc in milestone_collection.find().sort("time_in_minutes", 1):
        milestones.append(MilestoneSchema(**doc))
    return milestones

