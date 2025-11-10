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
    onboarding_id: Optional[PyObjectId] = None

    # ✅ RENAMED
    avatar_url: Optional[str] = None

    # ✅ NEW username fields
    username: Optional[str] = None      # stored with leading "@", e.g. "@stephenBgomes"
    username_lc: Optional[str] = None   # lowercased copy, for uniqueness checks

    created_at: datetime = Field(default_factory=datetime.utcnow)
    apns_token: Optional[str] = None
    socket_ids: List[str] = []

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        # Important for legacy docs that may still have 'memoji_url'
        "extra": "ignore",
    }
