from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# Convert ObjectId to string for safe serialization
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]


# ✅ Embedded data classes
class BackupRequest(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CheckInNudge(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MotivationHit(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ✅ Create schema
class FriendCreate(BaseModel):
    friend_id: PyObjectId
    friends_list: List[PyObjectId] = Field(default_factory=list)
    friend_quit_date: Optional[datetime] = None
    friend_login_streak: int = 0
    friend_aura: int = 0
    backup_requests: List[BackupRequest] = Field(default_factory=list)
    check_in_nudges: List[CheckInNudge] = Field(default_factory=list)
    motivation_hits: List[MotivationHit] = Field(default_factory=list)


# ✅ Update schema
class FriendUpdate(BaseModel):
    friends_list: Optional[List[PyObjectId]] = None
    friend_quit_date: Optional[datetime] = None
    friend_login_streak: Optional[int] = None
    friend_aura: Optional[int] = None
    backup_requests: Optional[List[BackupRequest]] = None
    check_in_nudges: Optional[List[CheckInNudge]] = None
    motivation_hits: Optional[List[MotivationHit]] = None


# ✅ Response schema
class FriendResponse(FriendCreate):
    id: str
    user_id: str
