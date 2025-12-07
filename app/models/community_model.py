# app/models/community_model.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]


class CommentModel(BaseModel):
    comment_text: str
    comment_author_id: PyObjectId
    comment_timestamp: datetime = Field(default_factory=datetime.utcnow)


class PostModel(BaseModel):
    post_text: str
    post_author_id: PyObjectId
    post_visibility: str  # "community" or "friends_only"
    post_timestamp: datetime = Field(default_factory=datetime.utcnow)
    likes_count: int = 0
    liked_by: List[PyObjectId] = Field(default_factory=list)
    comments: List[CommentModel] = Field(default_factory=list)


class UserSocialStatsModel(BaseModel):
    posts: int = 0
    likes_given: int = 0
    comments: int = 0


class CommunityModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    posts: List[PostModel] = Field(default_factory=list)
    user_social_stats: UserSocialStatsModel = UserSocialStatsModel()
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
