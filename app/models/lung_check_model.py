# app/models/lung_check_model.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class LungCheckEntry(BaseModel):
    timestamp: datetime
    duration: float  # Duration in seconds

class LungCheckModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId  # Reference to authenticated user
    lung_check_history: List[LungCheckEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
