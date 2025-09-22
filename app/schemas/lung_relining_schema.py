# app/schemas/lung_relining_schema.py
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class LungReliningCreateRequest(BaseModel):
    last_relapse_date: datetime
    quit_date: datetime

class LungReliningUpdateRequest(BaseModel):
    # Only this field is editable via the PATCH endpoint
    last_relapse_date: datetime

class LungReliningResponse(BaseModel):
    id: Optional[str] = None
    last_relapse_date: datetime
    quit_date: datetime
    delta_seconds: float
    percent_of_90_days: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    user: Dict[str, Optional[str]]  # {"id", "email", "name"}
