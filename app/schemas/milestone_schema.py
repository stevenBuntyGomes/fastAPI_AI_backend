# app/schemas/milestone_schema.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from ._base_datetime import NaiveIsoDatetimeModel

class MilestoneSchema(NaiveIsoDatetimeModel):
    name: str
    description: str
    time_in_minutes: int
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
