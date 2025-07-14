from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class LungReliningModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId  # Links to authenticated user
    last_relapse_date: datetime  # Used for healing stage calculation
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
