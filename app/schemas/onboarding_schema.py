# app/schemas/onboarding_schema.py

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from ._base_datetime import NaiveIsoDatetimeModel


class OnboardingRequest(BaseModel):
    # ENUM fields for AI context
    vaping_frequency: Optional[Literal["never", "occasionally", "daily"]] = None
    vaping_trigger: Optional[str] = None  # Example: "after meals", "before sleep"
    vaping_effect: Optional[str] = None   # Example: "relaxed", "focused", "numb"
    hides_vaping: Optional[Literal["Always", "Sometimes", "Rarely", "Never", "always", "sometimes", "rarely", "never"]] = None

    # Integer-based exposure and cost tracking
    vaping_years: Optional[int] = None
    vape_cost_usd: Optional[int] = None
    puff_count: Optional[int] = None
    vape_lifespan_days: Optional[int] = None

    # Quit attempts and analytics
    quit_attempts: Optional[Literal["yes", "no", "many"]] = None
    referral_source: Optional[str] = None

    # Profile & demographics
    first_name: Optional[str] = None
    gender: Optional[Literal["male", "female", "non-binary", "prefer not to say"]] = None
    age: Optional[int] = None


class OnboardingResponse(BaseModel):
    """
    Response returned by POST /onboarding
    """
    onboarding_id: str = Field(..., description="Inserted onboarding document id")


class OnboardingOut(NaiveIsoDatetimeModel):
    """
    Response returned by GET/PATCH /onboarding/{id}
    """
    id: str

    vaping_frequency: Optional[Literal["never", "occasionally", "daily"]] = None
    vaping_trigger: Optional[str] = None
    vaping_effect: Optional[str] = None
    hides_vaping: Optional[Literal["yes", "no", "sometimes"]] = None

    vaping_years: Optional[int] = None
    vape_cost_usd: Optional[int] = None
    puff_count: Optional[int] = None
    vape_lifespan_days: Optional[int] = None
    quit_attempts: Optional[Literal["yes", "no", "many"]] = None
    referral_source: Optional[str] = None

    first_name: Optional[str] = None
    gender: Optional[Literal["male", "female", "non-binary", "prefer not to say"]] = None
    age: Optional[int] = None

    created_at: datetime
    updated_at: Optional[datetime] = None
