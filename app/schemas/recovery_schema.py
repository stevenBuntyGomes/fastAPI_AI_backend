# app/schemas/recovery_schema.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RecoveryCreateRequest(BaseModel):
    last_relapse_date: datetime
    quit_date: Optional[datetime] = None

class UserPreview(BaseModel):
    id: str  # keep as plain string to avoid alias mismatch
    email: str
    name: Optional[str]

class RecoveryResponse(BaseModel):
    last_relapse_date: datetime
    quit_date: datetime
    recovery_percentage: float
    user: UserPreview
