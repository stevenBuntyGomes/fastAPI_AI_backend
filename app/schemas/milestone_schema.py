from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class MilestoneCreateRequest(BaseModel):
    milestones_unlocked: List[str]
    last_relapse_date: Optional[datetime]

class MilestoneResponse(BaseModel):
    milestones_unlocked: List[str]
    last_relapse_date: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True
