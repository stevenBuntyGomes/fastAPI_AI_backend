# app/schemas/lung_relining_schema.py
from pydantic import BaseModel
from datetime import datetime

class LungReliningCreateRequest(BaseModel):
    last_relapse_date: datetime

class LungReliningResponse(BaseModel):
    last_relapse_date: datetime
    created_at: datetime
    user: dict  # Will be populated manually with user info
