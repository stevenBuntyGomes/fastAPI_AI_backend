# app/schemas/friend.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator
from .auth_schema import UserOut

# Converts MongoDB ObjectId to string during serialization
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

# ---------- Embedded message types ----------
class BackupRequest(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class CheckInNudge(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MotivationHit(BaseModel):
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ---------- Main Friend Profile ----------
class FriendCreate(BaseModel):
    friend_id: PyObjectId
    friends_list: List[PyObjectId] = Field(default_factory=list)
    friend_quit_date: Optional[datetime] = None
    friend_login_streak: int = 0
    friend_aura: int = 0
    backup_requests: List[BackupRequest] = Field(default_factory=list)
    check_in_nudges: List[CheckInNudge] = Field(default_factory=list)
    motivation_hits: List[MotivationHit] = Field(default_factory=list)

class FriendUpdate(BaseModel):
    friends_list: Optional[List[PyObjectId]] = None
    friend_quit_date: Optional[datetime] = None
    friend_login_streak: Optional[int] = None
    friend_aura: Optional[int] = None
    backup_requests: Optional[List[BackupRequest]] = None
    check_in_nudges: Optional[List[CheckInNudge]] = None
    motivation_hits: Optional[List[MotivationHit]] = None

class FriendResponse(FriendCreate):
    id: str
    user_id: str

# ---------- Friend Requests ----------
class FriendRequestSend(BaseModel):
    to_user_id: PyObjectId

class FriendRequestAct(BaseModel):
    request_id: PyObjectId

class FriendRequestListQuery(BaseModel):
    status: Optional[Literal["pending", "accepted", "rejected", "canceled"]] = None
    role: Optional[Literal["received", "sent", "all"]] = "all"
    skip: int = 0
    limit: int = 20

class FriendRequestResponse(BaseModel):
    id: str
    from_user_id: str
    to_user_id: str
    status: str
    created_at: datetime
    updated_at: datetime

class UnfriendRequest(BaseModel):
    friend_user_id: PyObjectId

# ---------- Populated variants ----------
# Friend profile with populated friends_list (full UserOuts)
class FriendResponsePopulated(BaseModel):
    id: str
    user_id: str
    friend_id: Optional[PyObjectId] = None  # ← made optional for backward compatibility
    friends_list: List[UserOut] = Field(default_factory=list)
    friend_quit_date: Optional[datetime] = None
    friend_login_streak: int = 0
    friend_aura: int = 0
    backup_requests: List[BackupRequest] = Field(default_factory=list)
    check_in_nudges: List[CheckInNudge] = Field(default_factory=list)
    motivation_hits: List[MotivationHit] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

# Friend request with full users instead of IDs
class FriendRequestResponseFull(BaseModel):
    id: str
    from_user: UserOut
    to_user: UserOut
    status: str
    created_at: datetime
    updated_at: datetime
