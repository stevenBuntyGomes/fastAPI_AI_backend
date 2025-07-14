from fastapi import APIRouter, Body
from pydantic import EmailStr
from typing import Optional

from ..schemas.onboarding_schema import OnboardingRequest
from ..controllers.auth_controller import (
    send_verification_code,
    verify_email_and_register,
    login_with_email_password,
    login_with_google,
    login_with_apple,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ✅ Step 1: Send verification code to email
@router.post("/send-code", summary="Send email verification code")
async def send_code(email: EmailStr = Body(..., embed=True)):
    return await send_verification_code(email)


# ✅ Step 2: Verify code and register user (with onboarding)
@router.post("/register", summary="Register user after verifying email")
async def register_user(
    email: EmailStr = Body(...),
    code: str = Body(...),
    name: str = Body(...),
    password: str = Body(...),
    onboarding: OnboardingRequest = Body(...)
):
    return await verify_email_and_register(email, code, name, password, onboarding)


# ✅ Step 3: Login with email & password
@router.post("/login", summary="Login with email and password")
async def login_user(
    email: EmailStr = Body(...),
    password: str = Body(...)
):
    return await login_with_email_password(email, password)


# ✅ Step 4: Login with Google OAuth (optional onboarding for first-time users)
@router.post("/google", summary="Login with Google")
async def google_login(
    token_id: str = Body(..., embed=True),
    onboarding: Optional[OnboardingRequest] = Body(None)
):
    return await login_with_google(token_id, onboarding)


# ✅ Step 5: Login with Apple OAuth (optional onboarding for first-time users)
@router.post("/apple", summary="Login with Apple")
async def apple_login(
    identity_token: str = Body(..., embed=True),
    onboarding: Optional[OnboardingRequest] = Body(None)
):
    return await login_with_apple(identity_token, onboarding)
