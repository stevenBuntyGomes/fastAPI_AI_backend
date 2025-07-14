# app/schemas/progress_schema.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class LungCheckEntry(BaseModel):
    timestamp: datetime
    duration: float  # In seconds

class ProgressCreateRequest(BaseModel):
    last_relapse_date: datetime
    quit_date: Optional[datetime] = None
    days_tracked: Optional[List[datetime]] = []
    lung_check_history: Optional[List[LungCheckEntry]] = []
    milestones_unlocked: Optional[List[str]] = []

class ProgressResponse(BaseModel):
    user_id: str  # ✅ Now included for linking
    last_relapse_date: Optional[datetime]
    quit_date: Optional[datetime]
    days_tracked: List[datetime]
    lung_check_history: List[LungCheckEntry]
    milestones_unlocked: List[str]
    created_at: datetime
