from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class MilestoneModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId  # Linked to authenticated user
    milestones_unlocked: List[str] = Field(default_factory=list)  # List of milestone IDs or names
    last_relapse_date: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
