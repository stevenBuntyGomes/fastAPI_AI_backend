# app/schemas/onboarding_schema.py

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class OnboardingRequest(BaseModel):
    # ENUM fields for AI context
    vaping_frequency: Optional[Literal["never", "occasionally", "daily"]] = None
    vaping_trigger: Optional[str] = None  # Example: "after meals", "before sleep"
    vaping_effect: Optional[str] = None   # Example: "relaxed", "focused", "numb"
    hides_vaping: Optional[Literal["yes", "no", "sometimes"]] = None

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


class OnboardingResponse(OnboardingRequest):
    user: dict  # You can replace with UserOut if you want typed user info
    created_at: datetime
    updated_at: Optional[datetime] = None
