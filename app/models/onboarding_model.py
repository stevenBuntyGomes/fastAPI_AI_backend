# app/models/onboarding_model.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

class OnboardingModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId

    vaping_frequency: Optional[str]
    vaping_trigger: Optional[str]
    vaping_effect: Optional[str]
    hides_vaping: Optional[str]

    vaping_years: Optional[int]
    vape_cost_usd: Optional[int]
    puff_count: Optional[int]
    vape_lifespan_days: Optional[int]
    quit_attempts: Optional[str]
    referral_source: Optional[str]

    first_name: Optional[str]
    gender: Optional[str]
    age: Optional[int]

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
