from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RecoveryCreateRequest(BaseModel):
    last_relapse_date: datetime

class UserPreview(BaseModel):
    id: str
    email: str
    name: Optional[str]

class RecoveryResponse(BaseModel):
    last_relapse_date: datetime
    quit_date: datetime  # last_relapse_date + 90 days
    recovery_percentage: float  # % toward recovery
    user: UserPreview
