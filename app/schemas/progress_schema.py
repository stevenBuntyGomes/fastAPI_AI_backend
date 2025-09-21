# app/schemas/progress_schema.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ._base_datetime import NaiveIsoDatetimeModel

class MilestoneStatus(BaseModel):
    name: str
    description: str
    time_in_minutes: int
    progress_percent: Optional[float] = None  # Only used for in-progress milestone

class ProgressCreateRequest(BaseModel):
    last_relapse_date: datetime
    quit_date: Optional[datetime] = None
    days_tracked: Optional[List[datetime]] = []
    milestones_unlocked: Optional[List[str]] = []

class ProgressResponse(NaiveIsoDatetimeModel):
    user_id: str
    last_relapse_date: Optional[datetime]
    quit_date: Optional[datetime]
    days_tracked: List[datetime]
    milestones_unlocked: List[str]
    created_at: datetime

    latest_unlocked: Optional[MilestoneStatus]
    current_in_progress: Optional[MilestoneStatus]
    next_locked: Optional[MilestoneStatus]
    minutes_since_last_relapse: float
