from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# Mongo-safe ObjectId typing
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

# 🔹 One lung check entry
class LungCheckEntry(BaseModel):
    timestamp: datetime
    duration: float  # In seconds

# 🔹 Main model for storing in MongoDB + pagination support
class LungCheckModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    progress_id: Optional[PyObjectId] = None  # still included, but optional if not always used
    lung_check_history: List[LungCheckEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # ✅ Pagination support (optional fields)
    skip: Optional[int] = None
    limit: Optional[int] = None
    count: Optional[int] = None

    # ✅ Optional user metadata if needed in response
    user: Optional[dict] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}