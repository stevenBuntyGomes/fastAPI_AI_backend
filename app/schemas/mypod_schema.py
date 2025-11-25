# app/schemas/mypod_schema.py
from pydantic import BaseModel, Field
from typing import List, Optional
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator
from datetime import datetime

# ObjectId as string
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

# 🔹 Submodels
class LeaderboardEntry(BaseModel):
    user_id: PyObjectId
    username: str
    profile_picture: Optional[str] = None
    aura: int
    login_streak: int

class FriendMeta(BaseModel):
    user_id: PyObjectId
    username: str

    # ✅ New fields
    avatar_url: Optional[str] = None      # comes from users.avatar_url
    profile_picture: Optional[str] = None # legacy / fallback
    aura: Optional[int] = 0
    login_streak: int = 0

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",  # ignore any old fields that might still be in Mongo
    }

class BumpEntry(BaseModel):
    friend_id: PyObjectId
    timestamps: List[str] = Field(default_factory=list)

# 🔹 Main Schema
class MyPodModel(BaseModel):  # ✅ renamed from MyPodSchema
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    username: str
    profile_picture: Optional[str] = None
    aura: int = 0
    login_streak: int = 0
    rank: Optional[int] = None

    leaderboard_data: List[LeaderboardEntry] = Field(default_factory=list)
    friends_list: List[FriendMeta] = Field(default_factory=list)
    bump_history: List[BumpEntry] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: str},
    }
