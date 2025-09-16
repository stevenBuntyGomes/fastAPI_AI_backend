# app/routes/auth.py
from fastapi import APIRouter, Body, Depends
from pydantic import EmailStr

from ..controllers.auth_controller import (
    send_verification_code,
    verify_email_and_register,
    login_with_email_password,
    login_with_google,
    login_with_apple,
    fetch_onboarding_by_id,
    get_authenticated_user,
      add_aura_points,  # NEW
)
from ..schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    GoogleLoginRequest,
    AppleLoginRequest,
    AuthResponse,
    UserOut,
      AddAuraRequest,
        AuraUpdateResponse,  # for /auth/me
)
from ..schemas.onboarding_schema import OnboardingOut
from ..utils.auth_utils import get_current_user  # 🔐 token auth dependency


router = APIRouter(prefix="/auth", tags=["Auth"])

# ✅ Step 1: Send verification code to email
@router.post("/send-code", summary="Send email verification code")
async def send_code(email: EmailStr = Body(..., embed=True)):
    return await send_verification_code(email)

# ✅ Step 2: Verify code and register user (requires onboarding_id)
@router.post("/register", response_model=AuthResponse, summary="Register user after verifying email")
async def register_user(payload: RegisterRequest):
    return await verify_email_and_register(
        email=payload.email,
        code=payload.code,
        name=payload.name,
        password=payload.password,
        onboarding_id=payload.onboarding_id,
    )

# ✅ Step 3: Login with email & password (returns token + user info)
@router.post("/login", response_model=AuthResponse, summary="Login with email and password")
async def login_user(payload: LoginRequest):
    return await login_with_email_password(payload.email, payload.password)

# ✅ Step 4: Login with Google OAuth (optional onboarding_id for first-time users)
@router.post("/google", response_model=AuthResponse, summary="Login with Google")
async def google_login(payload: GoogleLoginRequest):
    return await login_with_google(payload.token_id, payload.onboarding_id)

# ✅ Step 5: Login with Apple OAuth (optional onboarding_id for first-time users)
@router.post("/apple", response_model=AuthResponse, summary="Login with Apple")
async def apple_login(payload: AppleLoginRequest):
    return await login_with_apple(payload.identity_token, payload.onboarding_id)

# ✅ Convenience: fetch onboarding by onboarding_id (auth namespace)
@router.get("/onboarding/{onboarding_id}", response_model=OnboardingOut, summary="Get onboarding by id")
async def get_onboarding_via_auth(onboarding_id: str):
    return await fetch_onboarding_by_id(onboarding_id)

# ✅ NEW: Get the authenticated user (requires Bearer token)
@router.get("/me", response_model=UserOut, summary="Get authenticated user")
async def get_me(current_user: dict = Depends(get_current_user)):
    # current_user is injected by token auth; map it to UserOut via controller
    return await get_authenticated_user(current_user)

# ✅ Add aura points to the authenticated user
@router.post("/aura/add", response_model=AuraUpdateResponse, summary="Increment authenticated user's aura")
async def add_aura(payload: AddAuraRequest, current_user: dict = Depends(get_current_user)):
    return await add_aura_points(current_user, payload.points)