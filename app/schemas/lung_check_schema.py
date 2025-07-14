# app/schemas/lung_check_schema.py

from pydantic import BaseModel
from typing import List
from datetime import datetime

class LungCheckEntry(BaseModel):
    timestamp: datetime
    duration: float  # in seconds

class LungCheckCreateRequest(BaseModel):
    lung_check_history: List[LungCheckEntry]

class LungCheckResponse(BaseModel):
    user_id: str
    lung_check_history: List[LungCheckEntry]
    created_at: datetime
