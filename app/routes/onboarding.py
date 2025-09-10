# app/routes/onboarding.py
from fastapi import APIRouter, status
from ..schemas.onboarding_schema import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingOut,
)
from ..controllers.onboarding_controller import (
    create_onboarding,
    get_onboarding,
    update_onboarding,
)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

@router.post(
    "/",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create onboarding (no user_id stored)",
)
async def create_onboarding_route(payload: OnboardingRequest) -> OnboardingResponse:
    return await create_onboarding(payload)

@router.get(
    "/{onboarding_id}",
    response_model=OnboardingOut,
    status_code=status.HTTP_200_OK,
    summary="Get onboarding by id",
)
async def get_onboarding_route(onboarding_id: str) -> OnboardingOut:
    return await get_onboarding(onboarding_id)

@router.patch(
    "/{onboarding_id}",
    response_model=OnboardingOut,
    status_code=status.HTTP_200_OK,
    summary="Update onboarding by id",
)
async def update_onboarding_route(onboarding_id: str, payload: OnboardingRequest) -> OnboardingOut:
    return await update_onboarding(onboarding_id, payload)
