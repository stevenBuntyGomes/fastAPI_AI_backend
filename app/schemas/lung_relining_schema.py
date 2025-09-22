from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class LungReliningCreateRequest(BaseModel):
    last_relapse_date: datetime
    quit_date: datetime

class LungReliningResponse(BaseModel):
    id: Optional[str] = None
    last_relapse_date: datetime
    quit_date: datetime
    delta_seconds: float
    percent_of_90_days: float
    created_at: datetime
    user: Dict[str, str]  # id, email, name
