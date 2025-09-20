# app/routes/auth.py

from typing import List
from fastapi import APIRouter, Body, Depends
from pydantic import EmailStr

from ..controllers.auth_controller import (
    # Auth flows
    send_verification_code,
    verify_email_and_register,
    login_with_email_password,
    login_with_google,
    login_with_apple,

    # Helpers / lookups
    fetch_onboarding_by_id,
    get_authenticated_user,
    get_user_by_id,

    # Mutations
    add_aura_points,
    set_login_streak,

    # Search
    search_users_by_name,
    delete_account,
)

from ..schemas.auth_schema import (
    # Requests
    RegisterRequest,
    LoginRequest,
    GoogleLoginRequest,
    AppleLoginRequest,
    AddAuraRequest,
    LoginStreakSetRequest,

    # Responses
    AuthResponse,
    UserOut,
    AuraUpdateResponse,
    LoginStreakUpdateResponse,
    DeleteAccountResponse,
)

from ..schemas.onboarding_schema import OnboardingOut
from ..utils.auth_utils import get_current_user


router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------
# Email verification & signup
# ---------------------------

@router.post("/send-code", summary="Send email verification code")
async def send_code(email: EmailStr = Body(..., embed=True)):
    """Send a 6-digit verification code to the given email."""
    return await send_verification_code(email)


@router.post("/register", response_model=AuthResponse, summary="Register user after verifying email")
async def register_user(payload: RegisterRequest):
    """Verify code, create user, and return JWT + user."""
    return await verify_email_and_register(
        email=payload.email,
        code=payload.code,
        name=payload.name,
        password=payload.password,
        onboarding_id=payload.onboarding_id,
    )


# -------------
# Login (Email)
# -------------

@router.post("/login", response_model=AuthResponse, summary="Login with email and password")
async def login_user(payload: LoginRequest):
    """Login using email/password credentials."""
    return await login_with_email_password(payload.email, payload.password)


# --------------
# Login (OAuth)
# --------------

@router.post("/google", response_model=AuthResponse, summary="Login with Google")
async def google_login(payload: GoogleLoginRequest):
    """Login or create user via Google OAuth token."""
    return await login_with_google(payload.token_id, payload.onboarding_id)


@router.post("/apple", response_model=AuthResponse, summary="Login with Apple")
async def apple_login(payload: AppleLoginRequest):
    """Login or create user via Apple identity token."""
    return await login_with_apple(payload.identity_token, payload.onboarding_id)


# ----------------------
# Onboarding convenience
# ----------------------

@router.get("/onboarding/{onboarding_id}", response_model=OnboardingOut, summary="Get onboarding by id")
async def get_onboarding_via_auth(onboarding_id: str):
    """Fetch onboarding document by id."""
    return await fetch_onboarding_by_id(onboarding_id)


# ---------------------
# Authenticated helpers
# ---------------------

@router.get("/me", response_model=UserOut, summary="Get authenticated user")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user (via JWT)."""
    return await get_authenticated_user(current_user)


# -------------------------
# Mutations on user profile
# -------------------------

@router.post("/aura/add", response_model=AuraUpdateResponse, summary="Increment authenticated user's aura")
async def add_aura(payload: AddAuraRequest, current_user: dict = Depends(get_current_user)):
    """Increment the caller's aura by a positive integer."""
    return await add_aura_points(current_user, payload.points)


@router.post(
    "/login-streak/set",
    response_model=LoginStreakUpdateResponse,
    summary="Set authenticated user's login_streak (send days_tracked.length)",
)
async def set_login_streak_route(
    payload: LoginStreakSetRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Frontend computes login_streak as `days_tracked.length` and sends it here.
    This sets (not increments) the caller's login_streak.
    """
    return await set_login_streak(current_user, payload.login_streak)


# -------------
# Search & Read
# -------------

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
    return await search_users_by_name(
        q=q,
        limit=limit,
        skip=skip,
        exclude_self=exclude_self,
        current_user=current_user,
    )


@router.get("/user/{user_id}", response_model=UserOut, summary="Get a user by id")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Return a normalized user for the given `user_id`.
    Requires authentication but is not restricted to self.
    """
    return await get_user_by_id(user_id)


@router.delete("/me", response_model=DeleteAccountResponse, summary="Delete my account")
async def delete_my_account(current_user: dict = Depends(get_current_user)):
    """
    Permanently delete the authenticated user's account and related data.
    """
    user_id = str(current_user["_id"])
    return await delete_account(user_id)


@router.delete("/user/{user_id}", response_model=DeleteAccountResponse, summary="(Admin) Delete a user by id")
async def delete_user_account(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Admin-only: Permanently delete a specific user's account and related data.
    """
    # TODO: enforce admin authorization here
    return await delete_account(user_id)

