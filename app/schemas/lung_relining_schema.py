from pydantic import BaseModel
from datetime import datetime
from ._base_datetime import NaiveIsoDatetimeModel
class LungReliningCreateRequest(BaseModel):
    last_relapse_date: datetime

class LungReliningResponse(NaiveIsoDatetimeModel):
    last_relapse_date: datetime
    created_at: datetime
    user: dict  # Will be populated manually with user info
