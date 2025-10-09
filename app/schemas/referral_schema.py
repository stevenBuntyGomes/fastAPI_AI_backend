# app/schemas/referral_schema.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# Store ObjectIds as strings in API responses
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]


class UserPreview(BaseModel):
    id: PyObjectId
    name: Optional[str] = None
    email: Optional[str] = None


class GenerateCodeResponse(BaseModel):
    code: str


class ApplyReferralRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=32)


class ApplyReferralResponse(BaseModel):
    applied: bool
    applied_at: Optional[datetime] = None
    discount_cents: int
    referrer: Optional[UserPreview] = None
    message: Optional[str] = None


class ReferralStatusResponse(BaseModel):
    has_applied: bool
    applied_code: Optional[str] = None
    applied_at: Optional[datetime] = None
    referrer: Optional[UserPreview] = None
    discount_cents: int = 0


class ReferralSummaryItem(BaseModel):
    referee: UserPreview
    code: str
    applied_at: datetime


class ReferralSummaryResponse(BaseModel):
    total: int
    items: List[ReferralSummaryItem]
