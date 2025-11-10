# app/schemas/social_achievement_schema.py
from typing import Dict, Optional, List
from pydantic import BaseModel
from datetime import datetime

class AchievementEntrySchema(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    unlocked: bool
    unlocked_at: Optional[datetime] = None
    progress: Optional[float] = 0.0
    progress_value: Optional[int] = 0
    progress_target: Optional[int] = None

class SocialAchievementsResponse(BaseModel):
    user_id: str
    achievements: Dict[str, AchievementEntrySchema]
    updated_at: Optional[datetime] = None

class SocialRecalcResponse(SocialAchievementsResponse):
    # same shape as SocialAchievementsResponse
    pass
