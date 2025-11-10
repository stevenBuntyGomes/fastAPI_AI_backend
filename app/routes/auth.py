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
    search_users_by_name_or_id,
    delete_account,

    # NEW / renamed
    link_onboarding_to_user,
    set_avatar,
    edit_profile,

    # NEW memoji presets
    list_memoji_presets,
    select_memoji_for_user,
)

from ..schemas.auth_schema import (
    # Requests
    RegisterRequest,
    LoginRequest,
    GoogleLoginRequest,
    AppleLoginRequest,
    AddAuraRequest,
    LoginStreakSetRequest,
    OnboardingLinkRequest,

    # Responses
    AuthResponse,
    UserOut,
    AuraUpdateResponse,
    LoginStreakUpdateResponse,
    DeleteAccountResponse,
    OnboardingLinkResponse,

    # Avatar + memoji presets
    SetAvatarRequest,
    EditProfileRequest,
    MemojiPresetsResponse,
    MemojiSelectRequest,
)
from ..schemas.onboarding_schema import OnboardingOut
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

# ---------------------------
# Email verification & signup
# ---------------------------

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

# -------------
# Login (Email)
# -------------
@router.post("/login", response_model=AuthResponse, summary="Login with email and password")
async def login_user(payload: LoginRequest):
    return await login_with_email_password(payload.email, payload.password)

# --------------
# Login (OAuth)
# --------------
@router.post("/google", response_model=AuthResponse, summary="Login with Google")
async def google_login(payload: GoogleLoginRequest):
    return await login_with_google(payload.token_id, payload.onboarding_id)

@router.post("/apple", response_model=AuthResponse, summary="Login with Apple")
async def apple_login(payload: AppleLoginRequest):
    return await login_with_apple(payload.identity_token, payload.onboarding_id)

# ----------------------
# Onboarding convenience
# ----------------------
@router.get("/onboarding/{onboarding_id}", response_model=OnboardingOut, summary="Get onboarding by id")
async def get_onboarding_via_auth(onboarding_id: str):
    return await fetch_onboarding_by_id(onboarding_id)

@router.post(
    "/onboarding_user",
    response_model=OnboardingLinkResponse,
    summary="Link onboarding_id to the authenticated user (expects user_id & onboarding_id)",
)
async def link_onboarding_user(
    payload: OnboardingLinkRequest,
    current_user: dict = Depends(get_current_user),
):
    user = await link_onboarding_to_user(payload.user_id, payload.onboarding_id, current_user)
    return OnboardingLinkResponse(user=user)

# ---------------------
# Authenticated helpers
# ---------------------
@router.get("/me", response_model=UserOut, summary="Get authenticated user")
async def get_me(current_user: dict = Depends(get_current_user)):
    return await get_authenticated_user(current_user)

# -------------------------
# Mutations on user profile
# -------------------------
@router.post("/aura/add", response_model=AuraUpdateResponse, summary="Increment authenticated user's aura")
async def add_aura(payload: AddAuraRequest, current_user: dict = Depends(get_current_user)):
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
    return await set_login_streak(current_user, payload.login_streak)

# -------------
# Search & Read
# -------------
@router.get("/users/search", response_model=List[UserOut], summary="Search users by name or exact id")
async def search_users(
    q: str,
    limit: int = 20,
    skip: int = 0,
    exclude_self: bool = True,
    current_user: dict = Depends(get_current_user),
):
    return await search_users_by_name_or_id(
        q=q, limit=limit, skip=skip, exclude_self=exclude_self, current_user=current_user
    )

@router.get("/user/{user_id}", response_model=UserOut, summary="Get a user by id")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    return await get_user_by_id(user_id)

@router.delete("/me", response_model=DeleteAccountResponse, summary="Delete my account")
async def delete_my_account(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    return await delete_account(user_id)

@router.delete("/user/{user_id}", response_model=DeleteAccountResponse, summary="(Admin) Delete a user by id")
async def delete_user_account(user_id: str, current_user: dict = Depends(get_current_user)):
    # TODO: enforce admin authorization here
    return await delete_account(user_id)

# ----------
# Avatar (kept endpoint path, changed field name)
# ----------
@router.post(
    "/profile/memoji",
    response_model=UserOut,
    summary="Set or clear avatar URL for the authenticated user (send { avatar_url })"
)
async def set_avatar_route(
    payload: SetAvatarRequest,
    current_user: dict = Depends(get_current_user),
):
    return await set_avatar(current_user, payload.avatar_url)

@router.patch(
    "/profile",
    response_model=UserOut,
    summary="Edit profile (update name, avatar URL, and/or username)"
)
async def edit_profile_route(
    payload: EditProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    return await edit_profile(current_user, payload.name, payload.avatar_url, payload.username)

# ----------
# Memoji Presets
# ----------
@router.get(
    "/memoji/presets",
    response_model=MemojiPresetsResponse,
    summary="List available memoji preset URLs from Cloudinary (configurable)"
)
async def memoji_presets():
    presets = await list_memoji_presets()
    return MemojiPresetsResponse(presets=presets)

@router.post(
    "/memoji/select",
    response_model=UserOut,
    summary="Set avatar to one of the memoji preset URLs"
)
async def memoji_select(payload: MemojiSelectRequest, current_user: dict = Depends(get_current_user)):
    return await select_memoji_for_user(current_user, payload.url)
