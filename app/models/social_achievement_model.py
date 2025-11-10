# app/models/social_achievement_model.py
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# Mongo ObjectId -> str for serialization
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class AchievementEntry(BaseModel):
    code: str                    # stable key, e.g. "first_friend"
    name: str                    # display name
    description: Optional[str] = None
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None
    progress: Optional[float] = 0.0          # 0..100
    progress_value: Optional[int] = 0        # raw numerator (e.g., 3 bumps)
    progress_target: Optional[int] = None    # raw target (e.g., 20 bumps)

class SocialAchievementsModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId

    # Flat dict keyed by 'code' -> AchievementEntry
    achievements: Dict[str, AchievementEntry] = Field(default_factory=dict)

    # Internal trackers for time-based achievements (e.g., #1 rank streak)
    meta: Dict[str, Optional[datetime]] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
