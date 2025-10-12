# app/schemas/auth_schema.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from typing_extensions import Annotated
from pydantic.functional_validators import BeforeValidator

# For MongoDB ObjectId support
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x))]

# ✅ Request Schemas
class SendCodeRequest(BaseModel):
    email: EmailStr

class RegisterRequest(BaseModel):
    email: EmailStr
    code: str
    name: str
    password: str
    login_streak: int = 0
    onboarding_id: Optional[str] = None  # ← NOW OPTIONAL for email registration

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    token_id: str
    onboarding_id: Optional[str] = None  # optional for first-time users

class AppleLoginRequest(BaseModel):
    identity_token: str
    onboarding_id: Optional[str] = None  # optional for first-time users

# NEW: link onboarding to a user after auth
class OnboardingLinkRequest(BaseModel):
    user_id: str
    onboarding_id: str

# ✅ Response Schemas
class UserOut(BaseModel):
    id: Optional[PyObjectId]
    email: EmailStr
    name: Optional[str]
    aura: int = 0
    login_streak: int = 0
    onboarding_id: Optional[PyObjectId] = None  # include onboarding_id

class AuthResponse(BaseModel):
    token: str
    user: UserOut

class LoginStreakSetRequest(BaseModel):
    login_streak: int  # send days_tracked.length from frontend (must be >= 0)

class LoginStreakUpdateResponse(BaseModel):
    message: Optional[str] = None
    login_streak: int
    user: UserOut

# ✅ New request for adding aura
class AddAuraRequest(BaseModel):
    points: int  # number of points to add (must be > 0)

# ✅ New response for updated aura + user
class AuraUpdateResponse(BaseModel):
    message: Optional[str] = None
    aura: int
    user: UserOut

class DeleteAccountResponse(BaseModel):
    message: str
    deleted_user_id: Optional[PyObjectId] = None

# NEW: explicit response when linking onboarding
class OnboardingLinkResponse(BaseModel):
    message: str = "✅ Onboarding linked"
    user: UserOut
