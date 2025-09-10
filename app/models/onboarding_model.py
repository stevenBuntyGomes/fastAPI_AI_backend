# app/models/onboarding_model.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class OnboardingModel(BaseModel):
    """
    DB model for onboarding documents (no user_id here anymore).
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    vaping_frequency: Optional[str] = None
    vaping_trigger: Optional[str] = None
    vaping_effect: Optional[str] = None
    hides_vaping: Optional[str] = None

    vaping_years: Optional[int] = None
    vape_cost_usd: Optional[int] = None
    puff_count: Optional[int] = None
    vape_lifespan_days: Optional[int] = None
    quit_attempts: Optional[str] = None
    referral_source: Optional[str] = None

    first_name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
