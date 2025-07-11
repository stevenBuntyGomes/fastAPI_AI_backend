from fastapi import APIRouter, Body, HTTPException
from pydantic import EmailStr
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
    """
    Sends a 6-digit verification code to the user's email.
    """
    return await send_verification_code(email)

# ✅ Step 2: Verify code and register user
@router.post("/register", summary="Register user after verifying email")
async def register_user(
    email: EmailStr = Body(...),
    code: str = Body(...),
    name: str = Body(...),
    password: str = Body(...)
):
    """
    Registers a new user after verifying the 6-digit code sent via email.
    """
    return await verify_email_and_register(email, code, name, password)

# ✅ Step 3: Login with email & password
@router.post("/login", summary="Login with email and password")
async def login_user(
    email: EmailStr = Body(...),
    password: str = Body(...)
):
    """
    Logs in a user with email and password. Returns JWT and user info.
    """
    return await login_with_email_password(email, password)

# ✅ Step 4: Login with Google OAuth
@router.post("/google", summary="Login with Google")
async def google_login(token_id: str = Body(..., embed=True)):
    """
    Logs in a user using a Google OAuth token.
    """
    return await login_with_google(token_id)

# ✅ Step 5: Login with Apple OAuth
@router.post("/apple", summary="Login with Apple")
async def apple_login(identity_token: str = Body(..., embed=True)):
    """
    Logs in a user using an Apple identity token.
    """
    return await login_with_apple(identity_token)
