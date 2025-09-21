from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ._base_datetime import NaiveIsoDatetimeModel

class RecoveryCreateRequest(BaseModel):
    last_relapse_date: datetime
    quit_date: Optional[datetime] = None

class UserPreview(BaseModel):
    id: str  # ✅ Removed alias to avoid pydantic mismatch
    email: str
    name: Optional[str]

class RecoveryResponse(NaiveIsoDatetimeModel):
    last_relapse_date: datetime
    quit_date: datetime
    recovery_percentage: float
    user: UserPreview
