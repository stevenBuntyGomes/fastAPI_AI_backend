# app/models/progress_model.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class ProgressModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId  # Links to the authenticated user
    last_relapse_date: Optional[datetime] = None
    quit_date: Optional[datetime] = None
    days_tracked: List[datetime] = Field(default_factory=list)
    milestones_unlocked: List[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }