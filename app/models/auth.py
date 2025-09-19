# app/models/auth.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# ✅ Converts ObjectId to string before validation
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    email: EmailStr
    name: Optional[str] = None
    password: Optional[str] = None
    auth_provider: str = "email"
    aura: int = 0
    login_streak: int = 0
    onboarding_id: Optional[PyObjectId] = None  # ← NEW: store onboarding_id on the user
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # NEW (optional but handy)
    apns_token: Optional[str] = None       # iOS push token
    socket_ids: List[str] = []             # currently active socket.io sids

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
