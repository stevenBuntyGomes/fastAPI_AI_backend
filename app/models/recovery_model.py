from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class RecoveryModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId  # Authenticated user reference
    last_relapse_date: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
