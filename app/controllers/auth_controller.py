# app/controllers/auth_controller.py
from typing import Optional, List
from fastapi import HTTPException, status
from pydantic import EmailStr
from datetime import datetime, timedelta
from bson import ObjectId
import random
import re  # ← NEW

from ..models.auth import UserModel
from ..db.mongo import (
    users_collection,
    verification_codes_collection,
    onboarding_collection,
)
from ..utils.jwt_utils import create_jwt_token
from ..utils.hashing import hash_password, verify_password
from ..services.email_service import send_email_verification_code
from ..services.oauth_utils import verify_google_token, verify_apple_token
from ..schemas.auth_schema import AuthResponse, UserOut

# -----------------------
# STEP 1: Send code
# -----------------------
async def send_verification_code(email: EmailStr):
    code = str(random.randint(100000, 999999))
    await verification_codes_collection.update_one(
        {"email": email},
        {"$set": {"code": code, "expires": datetime.utcnow() + timedelta(minutes=10)}},
        upsert=True
    )
    await send_email_verification_code(email, code)
    return {"message": "📧 Verification code sent."}

# -----------------------
# STEP 2: Register (with onboarding_id provided by frontend)
# -----------------------
async def verify_email_and_register(
    email: EmailStr,
    code: str,
    name: str,
    password: str,
    onboarding_id: str,
) -> AuthResponse:
    record = await verification_codes_collection.find_one({"email": email})
    if not record or record["code"] != code:
        raise HTTPException(status_code=400, detail="❌ Invalid or expired code.")
    if datetime.utcnow() > record["expires"]:
        raise HTTPException(status_code=400, detail="⏰ Code expired.")
    if await users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="⚠️ User already exists.")

    try:
        ob_id = ObjectId(onboarding_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid onboarding_id format")
    onboarding_doc = await onboarding_collection.find_one({"_id": ob_id})
    if not onboarding_doc:
        raise HTTPException(status_code=400, detail="onboarding_id does not exist")

    hashed_pw = hash_password(password)
    result = await users_collection.insert_one({
        "email": email,
        "name": name,
        "password": hashed_pw,
        "auth_provider": "email",
        "aura": 0,
        "onboarding_id": ob_id,
        "created_at": datetime.utcnow()
    })

    await verification_codes_collection.delete_one({"email": email})

    user_out = UserOut(
        id=str(result.inserted_id),
        email=email,
        name=name,
        aura=0,
        onboarding_id=onboarding_id,
    )
    token = create_jwt_token({"user_id": str(result.inserted_id)})
    return AuthResponse(token=token, user=user_out)

# -----------------------
# STEP 3: Login with email & password
# -----------------------
async def login_with_email_password(email: EmailStr, password: str) -> AuthResponse:
    user_dict = await users_collection.find_one({"email": email})
    if not user_dict or not verify_password(password, user_dict.get("password", "")):
        raise HTTPException(status_code=401, detail="❌ Invalid credentials.")

    user = UserModel(**user_dict)
    user_out = UserOut(
        id=str(user.id) if user.id else None,
        email=user.email,
        name=user.name,
        aura=user.aura,
        onboarding_id=str(user.onboarding_id) if user.onboarding_id else None,
    )
    token = create_jwt_token({"user_id": str(user.id)})
    return AuthResponse(token=token, user=user_out)

# -----------------------
# STEP 4: Login with Google OAuth
# -----------------------
async def login_with_google(token_id: str, onboarding_id: Optional[str] = None) -> AuthResponse:
    payload = verify_google_token(token_id)
    if not payload:
        raise HTTPException(status_code=401, detail="❌ Invalid Google token.")

    email = payload["email"]
    name = payload.get("name", "Google User")

    user = await users_collection.find_one({"email": email})
    if not user:
        ob_obj: Optional[ObjectId] = None
        if onboarding_id:
            try:
                ob_obj = ObjectId(onboarding_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid onboarding_id format")
            if not await onboarding_collection.find_one({"_id": ob_obj}):
                raise HTTPException(status_code=400, detail="onboarding_id does not exist")

        result = await users_collection.insert_one({
            "email": email,
            "name": name,
            "auth_provider": "google",
            "aura": 0,
            "onboarding_id": ob_obj,
            "created_at": datetime.utcnow()
        })
        user = {"_id": result.inserted_id, "email": email, "name": name, "aura": 0, "onboarding_id": ob_obj}
    else:
        if onboarding_id and not user.get("onboarding_id"):
            try:
                ob_obj = ObjectId(onboarding_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid onboarding_id format")
            if not await onboarding_collection.find_one({"_id": ob_obj}):
                raise HTTPException(status_code=400, detail="onboarding_id does not exist")
            await users_collection.update_one({"_id": user["_id"]}, {"$set": {"onboarding_id": ob_obj}})
            user["onboarding_id"] = ob_obj

    token = create_jwt_token({"user_id": str(user["_id"])})
    user_out = UserOut(
        id=str(user["_id"]),
        email=user["email"],
        name=user.get("name"),
        aura=user.get("aura", 0),
        onboarding_id=str(user.get("onboarding_id")) if user.get("onboarding_id") else None,
    )
    return AuthResponse(token=token, user=user_out)

# -----------------------
# STEP 5: Login with Apple OAuth
# -----------------------
async def login_with_apple(identity_token: str, onboarding_id: Optional[str] = None) -> AuthResponse:
    payload = verify_apple_token(identity_token)
    if not payload:
        raise HTTPException(status_code=401, detail="❌ Invalid Apple token.")

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Apple token is valid but did not include an email. "
                   "Request the 'email' scope on the first Apple sign-in and send that token to the backend."
        )

    name = payload.get("name", "Apple User")

    user = await users_collection.find_one({"email": email})
    if not user:
        ob_obj: Optional[ObjectId] = None
        if onboarding_id:
            try:
                ob_obj = ObjectId(onboarding_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid onboarding_id format")
            if not await onboarding_collection.find_one({"_id": ob_obj}):
                raise HTTPException(status_code=400, detail="onboarding_id does not exist")

        result = await users_collection.insert_one({
            "email": email,
            "name": name,
            "auth_provider": "apple",
            "aura": 0,
            "onboarding_id": ob_obj,
            "created_at": datetime.utcnow()
        })
        user = {"_id": result.inserted_id, "email": email, "name": name, "aura": 0, "onboarding_id": ob_obj}
    else:
        if onboarding_id and not user.get("onboarding_id"):
            try:
                ob_obj = ObjectId(onboarding_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid onboarding_id format")
            if not await onboarding_collection.find_one({"_id": ob_obj}):
                raise HTTPException(status_code=400, detail="onboarding_id does not exist")
            await users_collection.update_one({"_id": user["_id"]}, {"$set": {"onboarding_id": ob_obj}})
            user["onboarding_id"] = ob_obj

    token = create_jwt_token({"user_id": str(user["_id"])})
    user_out = UserOut(
        id=str(user["_id"]),
        email=user["email"],
        name=user.get("name"),
        aura=user.get("aura", 0),
        onboarding_id=str(user.get("onboarding_id")) if user.get("onboarding_id") else None,
    )
    return AuthResponse(token=token, user=user_out)

# -----------------------
# Optional helper: fetch onboarding by onboarding_id (auth convenience)
# -----------------------
from ..models.onboarding_model import OnboardingModel
from ..schemas.onboarding_schema import OnboardingOut

async def fetch_onboarding_by_id(onboarding_id: str) -> OnboardingOut:
    try:
        ob_id = ObjectId(onboarding_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid onboarding id")

    doc = await onboarding_collection.find_one({"_id": ob_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding not found")

    model = OnboardingModel(**doc)
    return OnboardingOut(
        id=str(model.id) if model.id else "",
        vaping_frequency=model.vaping_frequency,
        vaping_trigger=model.vaping_trigger,
        vaping_effect=model.vaping_effect,
        hides_vaping=model.hides_vaping,
        vaping_years=model.vaping_years,
        vape_cost_usd=model.vape_cost_usd,
        puff_count=model.puff_count,
        vape_lifespan_days=model.vape_lifespan_days,
        quit_attempts=model.quit_attempts,
        referral_source=model.referral_source,
        first_name=model.first_name,
        gender=model.gender,
        age=model.age,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )

# -----------------------
# NEW: Get the authenticated user (for /auth/me)
# -----------------------
async def get_authenticated_user(current_user: dict) -> UserOut:
    return UserOut(
        id=str(current_user.get("_id")) if current_user.get("_id") else None,
        email=current_user.get("email"),
        name=current_user.get("name"),
        aura=current_user.get("aura", 0),
        onboarding_id=str(current_user.get("onboarding_id")) if current_user.get("onboarding_id") else None,
    )

# -----------------------
# NEW: Get a user by id (for iOS: supply user_id, get full user info)
# -----------------------
async def get_user_by_id(user_id: str) -> UserOut:
    # 1) Validate ObjectId
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    # 2) Fetch with a safe projection (only fields your app needs)
    projection = {
        "email": 1,
        "name": 1,
        "aura": 1,
        "login_streak": 1,          # ← include streak
        "onboarding_id": 1,
        "created_at": 1,
        "apns_token": 1,            # optional: surface if you want
        "socket_ids": 1,            # optional: surface if you want
    }
    doc = await users_collection.find_one({"_id": obj_id}, projection)

    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    # 3) Normalize as UserOut (defaults handle missing fields)
    return UserOut(
        id=str(doc["_id"]),
        email=doc.get("email"),
        name=doc.get("name"),
        aura=int(doc.get("aura", 0)),
        login_streak=int(doc.get("login_streak", 0)),
        onboarding_id=str(doc.get("onboarding_id")) if doc.get("onboarding_id") else None,
    )


# ✅ Add aura to the currently authenticated user
async def add_aura_points(current_user: dict, points: int):
    if not isinstance(points, int) or points <= 0:
        raise HTTPException(status_code=400, detail="points must be a positive integer")

    user_id = current_user.get("_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    await users_collection.update_one(
        {"_id": user_id},
        {"$inc": {"aura": points}, "$set": {"updated_at": datetime.utcnow()}}
    )

    updated = await users_collection.find_one({"_id": user_id})
    if not updated:
        raise HTTPException(status_code=404, detail="User not found after update")

    user_out = UserOut(
        id=str(updated["_id"]),
        email=updated.get("email"),
        name=updated.get("name"),
        aura=updated.get("aura", 0),
        login_streak=int(updated.get("login_streak", 0)),
        onboarding_id=str(updated.get("onboarding_id")) if updated.get("onboarding_id") else None,
    )
    return {"message": "✅ Aura updated", "aura": user_out.aura, "user": user_out}

# -----------------------
# NEW: Search users by name (substring, case-insensitive)
# -----------------------
async def search_users_by_name(
    q: str,
    limit: int = 20,
    skip: int = 0,
    exclude_self: bool = True,
    current_user: Optional[dict] = None,
) -> List[UserOut]:
    """
    Search users by `name` (case-insensitive substring).
    - `exclude_self`: True to omit the caller from results.
    - `limit`: capped to 50 for safety.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query `q` is required.")

    q = q.strip()
    limit = max(1, min(limit, 50))
    skip = max(0, skip)

    # Build Mongo query
    regex = {"$regex": re.escape(q), "$options": "i"}
    query = {"name": regex}

    if exclude_self and current_user and current_user.get("_id"):
        query["_id"] = {"$ne": current_user["_id"]}

    # Project only safe fields
    projection = {"email": 1, "name": 1, "aura": 1, "onboarding_id": 1}

    cursor = users_collection.find(query, projection).sort("name", 1).skip(skip).limit(limit)
    results: List[UserOut] = []
    async for doc in cursor:
        results.append(
            UserOut(
                id=str(doc["_id"]),
                email=doc.get("email"),
                name=doc.get("name"),
                aura=int(doc.get("aura", 0)),
                onboarding_id=str(doc.get("onboarding_id")) if doc.get("onboarding_id") else None,
            )
        )

    return results
