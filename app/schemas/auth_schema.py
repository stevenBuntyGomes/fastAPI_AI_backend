# app/schemas/auth_schema.py
from pydantic import BaseModel, EmailStr
from typing import Optional

class SendCodeRequest(BaseModel):
    email: EmailStr

class RegisterRequest(BaseModel):
    email: EmailStr
    code: str
    name: str
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class OAuthRequest(BaseModel):
    token_id: str  # for Google
    identity_token: Optional[str] = None  # for Apple

class UserOut(BaseModel):
    email: EmailStr
    name: Optional[str]

class AuthResponse(BaseModel):
    token: str
    user: UserOut
