from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator
from ._base_datetime import NaiveIsoDatetimeModel
# MongoDB ObjectId-safe string
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]


# 🔹 Individual lung check entry
class LungCheckEntry(BaseModel):
    timestamp: datetime
    duration: float  # in seconds


# 🔹 Request to submit lung check history (list of entries)
class LungCheckCreateRequest(BaseModel):
    lung_check_history: List[LungCheckEntry]


# 🔹 Response schema with Mongo-style ID
class LungCheckResponse(NaiveIsoDatetimeModel):
    id: PyObjectId = Field(alias="_id")
    user_id: PyObjectId
    lung_check_history: List[LungCheckEntry]
    created_at: datetime
    skip: int = 0
    limit: int = 7
