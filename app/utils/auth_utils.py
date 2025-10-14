# app/utils/auth_utils.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from bson import ObjectId

from ..db.mongo import users_collection

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
# Support either JWT_SECRET_KEY (yours) or JWT_SECRET (fallback)
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or ""
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Allowlist for Safety moderation admin (IDs or emails). If set, ONLY these can access.
_SAFETY_ADMIN_USER_IDS = {
    s.strip() for s in (os.getenv("SAFETY_ADMIN_USER_IDS", "") or "").split(",") if s.strip()
}
_SAFETY_ADMIN_EMAILS = {
    s.strip().lower() for s in (os.getenv("SAFETY_ADMIN_EMAILS", "") or "").split(",") if s.strip()
}

# Bearer scheme for typical HTTP routes
bearer_scheme = HTTPBearer(auto_error=True)
# Optional bearer (won't auto-raise) for endpoints where auth is optional
optional_bearer_scheme = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------
# Internal helper
# ------------------------------------------------------------------
async def _load_user_or_401(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # “Ejecting the user who provided the offending content” (Apple 1.2)
    if user.get("is_banned") is True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account banned.")

    if user.get("is_suspended") and user.get("suspended_until"):
        try:
            if user["suspended_until"] > datetime.utcnow():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended.")
        except Exception:
            # If stored value is not a datetime, ignore the comparison
            pass

    return user


# ------------------------------------------------------------------
# Public dependencies
# ------------------------------------------------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Validates Bearer JWT, loads the user, and enforces banned/suspended gates.
    Returns the Mongo user document (with ObjectId _id).
    """
    token = credentials.credentials
    if not SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWT secret not configured.")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    return await _load_user_or_401(user_id)


async def get_current_user_require_eula(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Same as get_current_user but also requires an accepted EULA.
    """
    user = await get_current_user(credentials)
    if not user.get("eula", {}).get("accepted", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please accept the EULA to use this feature.")
    return user


async def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Admin guard. Accepts either user.role == 'admin' or user.is_admin == True.
    """
    user = await get_current_user(credentials)
    if not (user.get("role") == "admin" or user.get("is_admin") is True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only.")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
):
    """
    Optional auth: returns a user doc if a valid Bearer token is present; otherwise returns None.
    Never raises for missing/invalid token—useful for public endpoints.
    """
    if not credentials:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return await _load_user_or_401(user_id)
    except Exception:
        return None


# ------------------------------------------------------------------
# Strict Safety-admin helpers (for Safety routes only)
# ------------------------------------------------------------------
def _is_safety_admin(user: dict) -> bool:
    """
    If SAFETY_ADMIN_* env vars are set, enforce a hard allowlist.
    Otherwise, fall back to the normal admin rule (role=='admin' or is_admin==True).
    """
    if _SAFETY_ADMIN_USER_IDS or _SAFETY_ADMIN_EMAILS:
        if str(user.get("_id")) in _SAFETY_ADMIN_USER_IDS:
            return True
        email = (user.get("email") or "").lower()
        if email and email in _SAFETY_ADMIN_EMAILS:
            return True
        return False

    # No allowlist configured => default admin rule
    return (user.get("role") == "admin") or (user.get("is_admin") is True)


async def get_moderation_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    STRICT admin for Safety routes.
    - If allowlist envs are set, only those users can pass.
    - Else: same behavior as get_current_admin_user.
    """
    user = await get_current_user(credentials)
    if not _is_safety_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only.")
    return user
