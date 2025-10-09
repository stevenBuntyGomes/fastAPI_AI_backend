# app/routes/referral.py
from fastapi import APIRouter, Depends
from ..utils.auth_utils import get_current_user

from ..schemas.referral_schema import (
    GenerateCodeResponse,
    ApplyReferralRequest,
    ApplyReferralResponse,
    ReferralStatusResponse,
    ReferralSummaryResponse,
)

from ..controllers.referral_controller import (
    ensure_referral_code,
    apply_referral,
    get_referral_status,
    list_my_referrals,
)

router = APIRouter(prefix="/referral", tags=["referral"])

@router.get("/code", response_model=GenerateCodeResponse, summary="Get or create my referral code")
async def get_or_create_code(current_user: dict = Depends(get_current_user)):
    return await ensure_referral_code(current_user)

@router.post("/apply", response_model=ApplyReferralResponse, summary="Apply a referral code to my account")
async def apply_code(payload: ApplyReferralRequest, current_user: dict = Depends(get_current_user)):
    return await apply_referral(payload.code, current_user)

@router.get("/status", response_model=ReferralStatusResponse, summary="My referral application status & wallet credit")
async def my_status(current_user: dict = Depends(get_current_user)):
    return await get_referral_status(current_user)

@router.get("/my", response_model=ReferralSummaryResponse, summary="Who used my code (as referrer)")
async def my_referrals(current_user: dict = Depends(get_current_user)):
    return await list_my_referrals(current_user)
