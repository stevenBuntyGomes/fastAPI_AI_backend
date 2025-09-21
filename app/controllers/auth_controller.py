# app/controllers/auth_controller.py
from typing import Optional, List
from fastapi import HTTPException, status
from pydantic import EmailStr
from datetime import datetime, timedelta
from bson import ObjectId
import random
import re

from ..models.auth import UserModel
from ..db.mongo import (
    users_collection,
    verification_codes_collection,
    onboarding_collection,
    progress_collection,
    recovery_collection,
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
        upsert=True,
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
    if not record or record.get("code") != code:
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
    result = await users_collection.insert_one(
        {
            "email": email,
            "name": name,
            "password": hashed_pw,
            "auth_provider": "email",
            "aura": 0,
            "login_streak": 0,  # ✅ initialize
            "onboarding_id": ob_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    await verification_codes_collection.delete_one({"email": email})

    user_out = UserOut(
        id=str(result.inserted_id),
        email=email,
        name=name,
        aura=0,
        login_streak=0,
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

    user = UserModel(**user_dict)  # for typed fields you already use
    user_out = UserOut(
        id=str(user.id) if user.id else None,
        email=user.email,
        name=user.name,
        aura=int(user_dict.get("aura") or 0),
        login_streak=int(user_dict.get("login_streak") or 0),  # ✅ include streak
        onboarding_id=str(user_dict.get("onboarding_id")) if user_dict.get("onboarding_id") else None,
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

        result = await users_collection.insert_one(
            {
                "email": email,
                "name": name,
                "auth_provider": "google",
                "aura": 0,
                "login_streak": 0,  # ✅ initialize
                "onboarding_id": ob_obj,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )
        user = {
            "_id": result.inserted_id,
            "email": email,
            "name": name,
            "aura": 0,
            "login_streak": 0,
            "onboarding_id": ob_obj,
        }
    else:
        if onboarding_id and not user.get("onboarding_id"):
            try:
                ob_obj = ObjectId(onboarding_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid onboarding_id format")
            if not await onboarding_collection.find_one({"_id": ob_obj}):
                raise HTTPException(status_code=400, detail="onboarding_id does not exist")
            await users_collection.update_one({"_id": user["_id"]}, {"$set": {"onboarding_id": ob_obj, "updated_at": datetime.utcnow()}})
            user["onboarding_id"] = ob_obj

    token = create_jwt_token({"user_id": str(user["_id"])})
    user_out = UserOut(
        id=str(user["_id"]),
        email=user["email"],
        name=user.get("name"),
        aura=int(user.get("aura") or 0),
        login_streak=int(user.get("login_streak") or 0),  # ✅ include streak
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
            detail=(
                "Apple token is valid but did not include an email. "
                "Request the 'email' scope on the first Apple sign-in and send that token to the backend."
            ),
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

        result = await users_collection.insert_one(
            {
                "email": email,
                "name": name,
                "auth_provider": "apple",
                "aura": 0,
                "login_streak": 0,  # ✅ initialize
                "onboarding_id": ob_obj,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )
        user = {
            "_id": result.inserted_id,
            "email": email,
            "name": name,
            "aura": 0,
            "login_streak": 0,
            "onboarding_id": ob_obj,
        }
    else:
        if onboarding_id and not user.get("onboarding_id"):
            try:
                ob_obj = ObjectId(onboarding_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid onboarding_id format")
            if not await onboarding_collection.find_one({"_id": ob_obj}):
                raise HTTPException(status_code=400, detail="onboarding_id does not exist")
            await users_collection.update_one({"_id": user["_id"]}, {"$set": {"onboarding_id": ob_obj, "updated_at": datetime.utcnow()}})
            user["onboarding_id"] = ob_obj

    token = create_jwt_token({"user_id": str(user["_id"])})
    user_out = UserOut(
        id=str(user["_id"]),
        email=user["email"],
        name=user.get("name"),
        aura=int(user.get("aura") or 0),
        login_streak=int(user.get("login_streak") or 0),  # ✅ include streak
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
# Get the authenticated user (for /auth/me)
# -----------------------
async def get_authenticated_user(current_user: dict) -> UserOut:
    uid = current_user.get("_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if isinstance(uid, str):
        try:
            uid = ObjectId(uid)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid auth user id")

    doc = await users_collection.find_one(
        {"_id": uid},
        {"email": 1, "name": 1, "aura": 1, "login_streak": 1, "onboarding_id": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut(
        id=str(doc["_id"]),
        email=doc.get("email"),
        name=doc.get("name"),
        aura=int(doc.get("aura") or 0),
        login_streak=int(doc.get("login_streak") or 0),
        onboarding_id=str(doc.get("onboarding_id")) if doc.get("onboarding_id") else None,
    )

# -----------------------
# Get a user by id
# -----------------------
async def get_user_by_id(user_id: str) -> UserOut:
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    projection = {
        "email": 1,
        "name": 1,
        "aura": 1,
        "login_streak": 1,
        "onboarding_id": 1,
        "created_at": 1,
        "apns_token": 1,
        "socket_ids": 1,
    }
    doc = await users_collection.find_one({"_id": obj_id}, projection)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut(
        id=str(doc["_id"]),
        email=doc.get("email"),
        name=doc.get("name"),
        aura=int(doc.get("aura") or 0),
        login_streak=int(doc.get("login_streak") or 0),
        onboarding_id=str(doc.get("onboarding_id")) if doc.get("onboarding_id") else None,
    )

# -----------------------
# Add aura to the currently authenticated user
# -----------------------
async def add_aura_points(current_user: dict, points: int):
    if not isinstance(points, int) or points <= 0:
        raise HTTPException(status_code=400, detail="points must be a positive integer")

    uid = current_user.get("_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if isinstance(uid, str):
        try:
            uid = ObjectId(uid)
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized")

    await users_collection.update_one(
        {"_id": uid},
        {"$inc": {"aura": points}, "$set": {"updated_at": datetime.utcnow()}},
    )

    updated = await users_collection.find_one({"_id": uid})
    if not updated:
        raise HTTPException(status_code=404, detail="User not found after update")

    user_out = UserOut(
        id=str(updated["_id"]),
        email=updated.get("email"),
        name=updated.get("name"),
        aura=int(updated.get("aura") or 0),
        login_streak=int(updated.get("login_streak") or 0),
        onboarding_id=str(updated.get("onboarding_id")) if updated.get("onboarding_id") else None,
    )
    return {"message": "✅ Aura updated", "aura": user_out.aura, "user": user_out}

# -----------------------
# Search users by name OR exact _id (exclusive modes)
# -----------------------
async def search_users_by_name_or_id(
    q: str,
    limit: int = 20,
    skip: int = 0,
    exclude_self: bool = True,
    current_user: Optional[dict] = None,
) -> List[UserOut]:
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query `q` is required.")

    q = q.strip()
    limit = max(1, min(limit, 50))
    skip = max(0, skip)

    # Normalize current user's id (string or ObjectId -> ObjectId)
    cur_oid: Optional[ObjectId] = None
    try:
        if current_user and current_user.get("_id"):
            cur_oid = ObjectId(str(current_user["_id"]))
    except Exception:
        cur_oid = None

    projection = {"email": 1, "name": 1, "aura": 1, "login_streak": 1, "onboarding_id": 1}

    # --- Mode A: exact _id match ---
    if ObjectId.is_valid(q):
        oid = ObjectId(q)
        # Respect exclude_self
        if exclude_self and cur_oid and cur_oid == oid:
            return []
        doc = await users_collection.find_one({"_id": oid}, projection)
        if not doc:
            return []
        return [
            UserOut(
                id=str(doc["_id"]),
                email=doc.get("email"),
                name=doc.get("name"),
                aura=int(doc.get("aura") or 0),
                login_streak=int(doc.get("login_streak") or 0),
                onboarding_id=str(doc.get("onboarding_id")) if doc.get("onboarding_id") else None,
            )
        ]

    # --- Mode B: name substring search (case-insensitive) ---
    name_regex = {"$regex": re.escape(q), "$options": "i"}
    name_query: dict = {"name": name_regex}
    if exclude_self and cur_oid:
        name_query["_id"] = {"$ne": cur_oid}

    cursor = (
        users_collection.find(name_query, projection)
        .sort("name", 1)
        .skip(skip)
        .limit(limit)
    )

    results: List[UserOut] = []
    async for doc in cursor:
        results.append(
            UserOut(
                id=str(doc["_id"]),
                email=doc.get("email"),
                name=doc.get("name"),
                aura=int(doc.get("aura") or 0),
                login_streak=int(doc.get("login_streak") or 0),
                onboarding_id=str(doc.get("onboarding_id")) if doc.get("onboarding_id") else None,
            )
        )
    return results

# -----------------------
# Utility: compute login streak from progress (distinct days)
# -----------------------
async def _compute_login_streak_from_progress(user_id_str: str) -> int:
    """
    Count DISTINCT calendar days in progress.days_tracked for this user.
    Accepts both datetime objects and ISO strings in the array.
    """
    progress = await progress_collection.find_one({"user_id": user_id_str}, {"days_tracked": 1})
    if not progress or not progress.get("days_tracked"):
        return 0

    unique_days = set()
    for entry in progress["days_tracked"]:
        if isinstance(entry, datetime):
            d = entry.date()
        else:
            try:
                d = datetime.fromisoformat(str(entry)).date()
            except Exception:
                continue
        unique_days.add(d)

    return len(unique_days)

# -----------------------
# Set login_streak to an exact value (sent from frontend)
# -----------------------
async def set_login_streak(current_user: dict, login_streak: int):
    if not isinstance(login_streak, int) or login_streak < 0:
        raise HTTPException(status_code=400, detail="login_streak must be a non-negative integer")

    uid = current_user.get("_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if isinstance(uid, str):
        try:
            uid = ObjectId(uid)
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized")

    await users_collection.update_one(
        {"_id": uid},
        {"$set": {"login_streak": login_streak, "updated_at": datetime.utcnow()}},
    )

    updated = await users_collection.find_one({"_id": uid})
    if not updated:
        raise HTTPException(status_code=404, detail="User not found after update")

    user_out = UserOut(
        id=str(updated["_id"]),
        email=updated.get("email"),
        name=updated.get("name"),
        aura=int(updated.get("aura") or 0),
        login_streak=int(updated.get("login_streak") or 0),  # ← your new value
        onboarding_id=str(updated.get("onboarding_id")) if updated.get("onboarding_id") else None,
    )

    return {"message": "✅ Login streak set", "login_streak": user_out.login_streak, "user": user_out}

# -----------------------
# Delete Account (hard delete)
# -----------------------
async def delete_account(user_id: str):
    """
    Hard-deletes the user's account and related data we own:
      - recovery_collection (by user_id)
      - progress_collection (by user_id)
      - users_collection (by _id)
    """
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    await recovery_collection.delete_many({"user_id": user_id})
    await progress_collection.delete_many({"user_id": user_id})

    res = await users_collection.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    # Best-effort cleanup of verification codes tied to any email (optional)
    await verification_codes_collection.delete_many({"email": {"$exists": True}})

    return {"message": "✅ Account and related data deleted.", "deleted_user_id": str(oid)}
