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

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class OAuthRequest(BaseModel):
    token_id: str  # For Google Login
    identity_token: Optional[str] = None  # For Apple Login


# ✅ Response Schemas
class UserOut(BaseModel):
    id: Optional[PyObjectId]
    email: EmailStr
    name: Optional[str]
    aura: int = 0  

class AuthResponse(BaseModel):
    token: str
    user: UserOut
