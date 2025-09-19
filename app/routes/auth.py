# app/routes/auth.py
from typing import List  # ← NEW
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
    get_user_by_id,
    add_aura_points,
    search_users_by_name,  # ← NEW
)
from ..schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    GoogleLoginRequest,
    AppleLoginRequest,
    AuthResponse,
    UserOut,
    AddAuraRequest,
    AuraUpdateResponse,
)
from ..schemas.onboarding_schema import OnboardingOut
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/send-code", summary="Send email verification code")
async def send_code(email: EmailStr = Body(..., embed=True)):
    return await send_verification_code(email)

@router.post("/register", response_model=AuthResponse, summary="Register user after verifying email")
async def register_user(payload: RegisterRequest):
    return await verify_email_and_register(
        email=payload.email,
        code=payload.code,
        name=payload.name,
        password=payload.password,
        onboarding_id=payload.onboarding_id,
    )

@router.post("/login", response_model=AuthResponse, summary="Login with email and password")
async def login_user(payload: LoginRequest):
    return await login_with_email_password(payload.email, payload.password)

@router.post("/google", response_model=AuthResponse, summary="Login with Google")
async def google_login(payload: GoogleLoginRequest):
    return await login_with_google(payload.token_id, payload.onboarding_id)

@router.post("/apple", response_model=AuthResponse, summary="Login with Apple")
async def apple_login(payload: AppleLoginRequest):
    return await login_with_apple(payload.identity_token, payload.onboarding_id)

@router.get("/onboarding/{onboarding_id}", response_model=OnboardingOut, summary="Get onboarding by id")
async def get_onboarding_via_auth(onboarding_id: str):
    return await fetch_onboarding_by_id(onboarding_id)

@router.get("/me", response_model=UserOut, summary="Get authenticated user")
async def get_me(current_user: dict = Depends(get_current_user)):
    return await get_authenticated_user(current_user)

@router.post("/aura/add", response_model=AuraUpdateResponse, summary="Increment authenticated user's aura")
async def add_aura(payload: AddAuraRequest, current_user: dict = Depends(get_current_user)):
    return await add_aura_points(current_user, payload.points)

# ------------- NEW: Search users by name -------------
@router.get("/users/search", response_model=List[UserOut], summary="Search users by name")
async def search_users(
    q: str,
    limit: int = 20,
    skip: int = 0,
    exclude_self: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """
    Case-insensitive substring search on `name`.
    Example: /auth/users/search?q=ali&limit=10
    """
    return await search_users_by_name(q=q, limit=limit, skip=skip, exclude_self=exclude_self, current_user=current_user)


# ------------- NEW: Get user by id -------------
@router.get("/user/{user_id}", response_model=UserOut, summary="Get a user by id")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Returns a normalized user document for the given `user_id`.
    Requires authentication but does not restrict to self.
    """
    return await get_user_by_id(user_id)