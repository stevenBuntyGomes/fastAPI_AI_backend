# app/models/milestone_model.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class MilestoneModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str  # e.g. "Heart Reset"
    description: str  # e.g. "Your heart rate and blood pressure start dropping..."
    time_in_minutes: int  # Time from relapse to unlock (e.g. 20, 120, 600)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
