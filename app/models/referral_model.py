# app/models/referral_model.py
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId
from typing import Optional
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class ReferralCodeModel(BaseModel):
    """
    One unique code per user (owner/referrer).
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    code: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }

class ReferralApplyModel(BaseModel):
    """
    One application per referee (the friend who uses a code).
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    referrer_user_id: PyObjectId
    referee_user_id: PyObjectId
    code: str
    discount_cents: int
    applied_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
