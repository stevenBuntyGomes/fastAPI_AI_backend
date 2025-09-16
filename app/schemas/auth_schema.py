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
    onboarding_id: str  # ← NEW: frontend sends onboarding_id created earlier

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    token_id: str
    onboarding_id: Optional[str] = None  # optional for first-time users

class AppleLoginRequest(BaseModel):
    identity_token: str
    onboarding_id: Optional[str] = None  # optional for first-time users


# ✅ Response Schemas
class UserOut(BaseModel):
    id: Optional[PyObjectId]
    email: EmailStr
    name: Optional[str]
    aura: int = 0
    onboarding_id: Optional[PyObjectId] = None  # ← include onboarding_id in responses

class AuthResponse(BaseModel):
    token: str
    user: UserOut



# ✅ New request for adding aura
class AddAuraRequest(BaseModel):
    points: int  # number of points to add (must be > 0)

# ✅ New response for updated aura + user
class AuraUpdateResponse(BaseModel):
    message: Optional[str] = None
    aura: int
    user: UserOut
