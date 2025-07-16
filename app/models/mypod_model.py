from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# MongoDB ObjectId → str during serialization
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]


# 🔹 Sub-models
class LeaderboardEntry(BaseModel):
    user_id: PyObjectId
    username: str
    profile_picture: Optional[str] = None
    aura: int
    login_streak: int


class FriendMeta(BaseModel):
    user_id: PyObjectId
    username: str
    profile_picture: Optional[str] = None
    aura: Optional[int] = 0


class BumpEntry(BaseModel):
    friend_id: PyObjectId
    timestamps: List[str] = Field(default_factory=list)  # ISO strings or formatted UTC


# 🔹 Main MyPodModel
class MyPodModel(BaseModel):
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
        "json_encoders": {ObjectId: str},
    }
