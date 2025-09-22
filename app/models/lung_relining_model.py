from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class LungReliningModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId                   # Authenticated user
    last_relapse_date: datetime           # Input
    quit_date: datetime                   # Input
    delta_seconds: float                  # Computed: (last_relapse_date - quit_date) in seconds
    percent_of_90_days: float            # Computed: (delta_seconds / 7_776_000) * 100
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
