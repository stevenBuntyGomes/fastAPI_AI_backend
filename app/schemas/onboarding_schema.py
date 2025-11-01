from pydantic import BaseModel, Field, field_validator, field_serializer, model_validator, ConfigDict
from typing import Optional, Literal
from datetime import datetime, timezone

# ----- Shared enum aliases -----
VapingFrequency = Literal["never", "occasionally", "daily"]
HidesVaping     = Literal["always", "sometimes", "rarely", "never"]
QuitAttempts    = Literal["yes", "no", "many"]
Gender          = Literal["male", "female", "non-binary", "prefer not to say"]
UseApp          = Literal["own", "family", "friends"]  # <— NEW


# ----- Base: normalize enum-ish strings to lowercase (model-level, safe in v2) -----
class _EnumNormaliser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _lower_enums(cls, values):
        if isinstance(values, dict):
            for k in ("vaping_frequency", "hides_vaping", "quit_attempts", "gender", "useapp"):
                v = values.get(k)
                if isinstance(v, str):
                    values[k] = v.strip().lower()
        return values


# ----- Request schema -----
class OnboardingRequest(_EnumNormaliser):
    vaping_frequency: Optional[VapingFrequency] = None
    vaping_trigger: Optional[str] = None
    vaping_effect: Optional[str] = None
    hides_vaping: Optional[HidesVaping] = None
    useapp: Optional[UseApp] = None  # <— NEW

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
            vv = v.strip()
            if vv.isdigit() or (vv.startswith("-") and vv[1:].isdigit()):
                return int(vv)
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
    useapp: Optional[UseApp] = None  # <— NEW

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

    # iOS-friendly ISO 8601: UTC, no fractional seconds, 'Z' suffix
    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, dt: Optional[datetime], _info):
        if dt is None:
            return None
        # ensure tz-aware UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc).replace(microsecond=0)
        # "2025-10-23T20:15:33Z" (works with JSONDecoder .iso8601)
        return dt.isoformat().replace("+00:00", "Z")
