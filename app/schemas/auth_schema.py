from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
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
    onboarding_id: Optional[str] = None  # optional for email registration

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    token_id: str
    onboarding_id: Optional[str] = None

class AppleLoginRequest(BaseModel):
    identity_token: str
    full_name: Optional[str] = None   # 👈 NEW – name coming from iOS
    onboarding_id: Optional[str] = None


# ✅ RENAMED: Set avatar (kept route path /auth/profile/memoji)
class SetAvatarRequest(BaseModel):
    avatar_url: Optional[str] = None  # None or "" clears it

    @field_validator("avatar_url", mode="before")
    @classmethod
    def _trim_accept_legacy(cls, v):
        # Accept both avatar_url and (legacy) memoji_url if client still sends it
        if v is None:
            return None
        v = str(v).strip()
        return v or None

class EditProfileRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None   # ✅ RENAMED
    username: Optional[str] = None

    @field_validator("name", "avatar_url", "username", mode="before")
    @classmethod
    def _trim(cls, v):
        if v is None:
            return None
        v = str(v).strip()
        return v or None

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
    onboarding_id: Optional[PyObjectId] = None
    avatar_url: Optional[str] = None   # ✅ RENAMED
    username: Optional[str] = None

class AuthResponse(BaseModel):
    token: str
    user: UserOut

class LoginStreakSetRequest(BaseModel):
    login_streak: int  # >= 0

class LoginStreakUpdateResponse(BaseModel):
    message: Optional[str] = None
    login_streak: int
    user: UserOut

# ✅ Add aura
class AddAuraRequest(BaseModel):
    points: int

# ✅ Updated aura response
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

# ---------- Upload schemas ----------
class Base64ImageUploadRequest(BaseModel):
    image_base64: str
    folder: Optional[str] = None

class ImageUploadResponse(BaseModel):
    url: str
    public_id: Optional[str] = None

# ---------- Memoji preset selection ----------
class MemojiPresetsResponse(BaseModel):
    presets: List[str]

class MemojiSelectRequest(BaseModel):
    url: str

    @field_validator("url", mode="before")
    @classmethod
    def _trim_url(cls, v):
        v = str(v or "").strip()
        if not v:
            raise ValueError("url is required")
        return v
