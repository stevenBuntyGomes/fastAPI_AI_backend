from pydantic import BaseModel, Field, field_validator, field_serializer, ConfigDict
from typing import Optional, Literal
from datetime import datetime, timezone

# ----- Shared enum aliases -----
VapingFrequency = Literal["never", "occasionally", "daily"]
HidesVaping     = Literal["always", "sometimes", "rarely", "never"]
QuitAttempts    = Literal["yes", "no", "many"]
Gender          = Literal["male", "female", "non-binary", "prefer not to say"]


# ----- Base: normalize enum-ish strings to lowercase -----
class _EnumNormaliser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @field_validator("vaping_frequency", "hides_vaping", "quit_attempts", "gender", mode="before")
    @classmethod
    def _lower_enums(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v


# ----- Request schema -----
class OnboardingRequest(_EnumNormaliser):
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

    # Be forgiving if frontend accidentally sends numeric strings
    @field_validator("vaping_years", "vape_cost_usd", "puff_count", "vape_lifespan_days", "age", mode="before")
    @classmethod
    def _to_int(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
                return int(v)
        return v


# ----- POST response (id only) -----
class OnboardingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    onboarding_id: str = Field(..., description="Inserted onboarding document id")


# ----- GET/PATCH response -----
class OnboardingOut(_EnumNormaliser):
    id: str

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

    created_at: datetime
    updated_at: Optional[datetime] = None

    # iOS-friendly ISO 8601 with timezone information
    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, dt: Optional[datetime], _info):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
