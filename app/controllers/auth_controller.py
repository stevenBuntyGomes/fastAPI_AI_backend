# app/controllers/auth_controller.py
from fastapi import HTTPException, status
from pydantic import EmailStr
from datetime import datetime, timedelta
import random
from ..models.auth import UserModel
from ..db.mongo import users_collection, verification_codes_collection
from ..utils.jwt import create_jwt_token
from ..utils.hashing import hash_password, verify_password
from ..services.email_service import send_email_verification_code
from ..services.oauth_utils import verify_google_token, verify_apple_token

from ..schemas.auth_schema import AuthResponse, UserOut

# STEP 1
async def send_verification_code(email: EmailStr):
    code = str(random.randint(100000, 999999))
    await verification_codes_collection.update_one(
        {"email": email},
        {"$set": {"code": code, "expires": datetime.utcnow() + timedelta(minutes=10)}},
        upsert=True
    )
    await send_email_verification_code(email, code)
    return {"message": "📧 Verification code sent."}

# STEP 2
async def verify_email_and_register(email: EmailStr, code: str, name: str, password: str) -> AuthResponse:
    record = await verification_codes_collection.find_one({"email": email})
    if not record or record["code"] != code:
        raise HTTPException(status_code=400, detail="❌ Invalid or expired code.")
    if datetime.utcnow() > record["expires"]:
        raise HTTPException(status_code=400, detail="⏰ Code expired.")
    if await users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="⚠️ User already exists.")

    hashed_pw = hash_password(password)
    result = await users_collection.insert_one({
        "email": email,
        "name": name,
        "password": hashed_pw,
        "auth_provider": "email",
        "created_at": datetime.utcnow()
    })

    token = create_jwt_token({"user_id": str(result.inserted_id)})
    return {"token": token, "user": {"email": email, "name": name}}

# STEP 3
# STEP 3: Login with Email/Password
async def login_with_email_password(email: EmailStr, password: str):
    user_dict = await users_collection.find_one({"email": email})
    if not user_dict or not verify_password(password, user_dict.get("password", "")):
        raise HTTPException(status_code=401, detail="❌ Invalid credentials.")

    # ✅ Parse DB data into a model
    user = UserModel(**user_dict)

    token = create_jwt_token({"user_id": str(user.id)})

    # ✅ Return only safe fields via UserOut schema
    return {
        "token": token,
        "user": UserOut(**user.dict())  # Converts model → safe schema
    }


# STEP 4
async def login_with_google(token_id: str) -> AuthResponse:
    payload = verify_google_token(token_id)
    if not payload:
        raise HTTPException(status_code=401, detail="❌ Invalid Google token.")
    email = payload["email"]
    name = payload.get("name", "Google User")
    user = await users_collection.find_one({"email": email})
    if not user:
        result = await users_collection.insert_one({
            "email": email,
            "name": name,
            "auth_provider": "google",
            "created_at": datetime.utcnow()
        })
        user = {"_id": result.inserted_id, "email": email, "name": name}
    token = create_jwt_token({"user_id": str(user["_id"])})
    return {"token": token, "user": {"email": user["email"], "name": user["name"]}}

# STEP 5
async def login_with_apple(identity_token: str) -> AuthResponse:
    payload = verify_apple_token(identity_token)
    if not payload:
        raise HTTPException(status_code=401, detail="❌ Invalid Apple token.")
    email = payload["email"]
    name = payload.get("name", "Apple User")
    user = await users_collection.find_one({"email": email})
    if not user:
        result = await users_collection.insert_one({
            "email": email,
            "name": name,
            "auth_provider": "apple",
            "created_at": datetime.utcnow()
        })
        user = {"_id": result.inserted_id, "email": email, "name": name}
    token = create_jwt_token({"user_id": str(user["_id"])})
    return {"token": token, "user": {"email": user["email"], "name": user["name"]}}
