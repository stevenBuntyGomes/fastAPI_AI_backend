from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# Import enum aliases from schema to keep a single source of truth
from app.schemas.onboarding_schema import (
    VapingFrequency, HidesVaping, QuitAttempts, Gender
)

PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]


class OnboardingModel(BaseModel):
    """
    Internal DB model (mirrors stored Mongo fields).
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        extra="ignore",
    )

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    vaping_frequency: Optional[VapingFrequency] = None
    vaping_trigger: Optional[str] = None
    vaping_effect: Optional[str] = None
    hides_vaping: Optional[HidesVaping] = None

    vaping_years: Optional[int] = None
    vape_cost_usd: Optional[int] = None
    puff_count: Optional[int] = None
    vape_lifespan_days: Optional[int] = None
    quit_attempts: Optional[QuitAttempts] = None
    referral_source: Optional[str] = None

    first_name: Optional[str] = None
    gender: Optional[Gender] = None
    age: Optional[int] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    # Make sure any legacy/naive timestamps read from DB become TZ-aware
    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_tz(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            # Accept ISO strings; normalize 'Z' to +00:00
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                return v
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
