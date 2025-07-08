# models/auth.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class User(BaseModel):
    email: EmailStr
    name: str
    hashed_password: Optional[str] = None  # For normal signup
    google_id: Optional[str] = None        # For Google login
    apple_id: Optional[str] = None         # For Apple login
    onboarding: Optional[dict] = None  # <-- Add this
    created_at: datetime = Field(default_factory=datetime.utcnow)
