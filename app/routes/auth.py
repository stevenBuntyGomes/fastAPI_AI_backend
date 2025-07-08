from fastapi import APIRouter, HTTPException, status, Body, Depends
from pydantic import EmailStr
from ..controllers.auth_controller import (
    send_verification_code,
    verify_email_and_register,
    login_with_email_password,
    login_with_google,
    login_with_apple
)

router = APIRouter(prefix="/auth", tags=["Auth"])

# Step 1: Send verification code to email
@router.post("/send-code")
async def send_code(email: EmailStr = Body(...)):
    return await send_verification_code(email)

# Step 2: Verify code and register user
@router.post("/register")
async def register_user(
    email: EmailStr = Body(...),
    code: str = Body(...),
    name: str = Body(...),
    password: str = Body(...)
):
    return await verify_email_and_register(email, code, name, password)

# Step 3: Login using email/password
@router.post("/login")
async def login_user(
    email: EmailStr = Body(...),
    password: str = Body(...)
):
    return await login_with_email_password(email, password)

# Step 4: Login using Google
@router.post("/google")
async def google_login(token_id: str = Body(...)):
    return await login_with_google(token_id)

# Step 5: Login using Apple
@router.post("/apple")
async def apple_login(identity_token: str = Body(...)):
    return await login_with_apple(identity_token)
