# app/routes/onboarding.py
from fastapi import APIRouter, status, Path
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

# Validate ObjectId-like path (prevents accidental 422/HTML decoding on the client)
ONBOARDING_ID = Path(
    ...,
    description="MongoDB ObjectId (24 hex chars)",
    min_length=24,
    max_length=24,
    pattern=r"^[a-fA-F0-9]{24}$",
)

@router.post(
    "/",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create onboarding (no user_id stored)",
    responses={
        201: {"description": "Onboarding created"},
        422: {"description": "Validation error"},
    },
)
async def create_onboarding_route(payload: OnboardingRequest) -> OnboardingResponse:
    return await create_onboarding(payload)

@router.get(
    "/{onboarding_id}",
    response_model=OnboardingOut,
    response_model_exclude_none=True,  # hide nulls for a cleaner client decode
    status_code=status.HTTP_200_OK,
    summary="Get onboarding by id",
    responses={
        200: {"description": "Onboarding found"},
        400: {"description": "Invalid onboarding id"},
        404: {"description": "Onboarding not found"},
    },
)
async def get_onboarding_route(onboarding_id: str = ONBOARDING_ID) -> OnboardingOut:
    return await get_onboarding(onboarding_id)

@router.patch(
    "/{onboarding_id}",
    response_model=OnboardingOut,
    response_model_exclude_none=True,  # hide nulls for a cleaner client decode
    status_code=status.HTTP_200_OK,
    summary="Update onboarding by id",
    responses={
        200: {"description": "Onboarding updated"},
        400: {"description": "Invalid onboarding id / No fields to update"},
        404: {"description": "Onboarding not found"},
        422: {"description": "Validation error"},
    },
)
async def update_onboarding_route(
    onboarding_id: str = ONBOARDING_ID,
    payload: OnboardingRequest = ...,
) -> OnboardingOut:
    return await update_onboarding(onboarding_id, payload)
