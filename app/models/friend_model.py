from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# Converts MongoDB ObjectId to string during serialization
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]


# 🔹 Embedded message types
class BackupRequest(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CheckInNudge(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MotivationHit(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# 🔹 Main Friend Profile model
class FriendProfileModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    friends_list: List[PyObjectId] = Field(default_factory=list)

    friend_quit_date: Optional[datetime] = None
    friend_login_streak: int = 0
    friend_aura: int = 0

    backup_requests: List[BackupRequest] = Field(default_factory=list)
    check_in_nudges: List[CheckInNudge] = Field(default_factory=list)
    motivation_hits: List[MotivationHit] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
