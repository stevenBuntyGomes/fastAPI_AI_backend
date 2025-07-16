from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CommentCreateRequest(BaseModel):
    comment_text: str

# Comment Schema
class CommentSchema(BaseModel):
    comment_text: str
    comment_author_id: str
    comment_timestamp: Optional[datetime] = None


# Post Schema
class PostSchema(BaseModel):
    post_text: str
    post_author_id: str
    post_visibility: str
    post_timestamp: Optional[datetime] = None
    likes_count: int = 0
    liked_by: List[str] = []
    comments: List[CommentSchema] = []


# User Social Stats
class UserSocialStatsSchema(BaseModel):
    posts: int = 0
    likes_given: int = 0
    comments: int = 0


# Full Community Schema
class CommunitySchema(BaseModel):
    user_id: str
    posts: List[PostSchema] = []
    user_social_stats: UserSocialStatsSchema = UserSocialStatsSchema()
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Post Update Schema
class PostUpdateRequest(BaseModel):
    post_text: Optional[str] = None
    post_visibility: Optional[str] = None

class PostCreateRequest(BaseModel):
    post_text: str
    post_visibility: str  # e.g., "community" or "friends_only"


class PostResponse(BaseModel):
    id: str  # assuming MongoDB ObjectId will be serialized as string
    post_text: str
    post_author_id: str
    post_visibility: str
    post_timestamp: Optional[datetime] = None
    likes_count: int = 0
    liked_by: List[str] = []
    comments: List[CommentSchema] = []
