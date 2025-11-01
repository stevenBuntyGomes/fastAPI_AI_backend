# app/controllers/onboarding_controller.py

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from bson import ObjectId
from pymongo import ReturnDocument

from ..db.mongo import onboarding_collection
from ..schemas.onboarding_schema import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingOut,
)

# -------------------------
# Helpers
# -------------------------

def _validate_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid onboarding id",
        )

_ENUM_KEYS = {"vaping_frequency", "hides_vaping", "quit_attempts", "gender", "useapp"}  # <— NEW

def _normalize_enums(d: Dict[str, Any]) -> None:
    """Lowercase/trim enum-like fields so they match Literal types."""
    for k in _ENUM_KEYS:
        v = d.get(k)
        if isinstance(v, str):
            d[k] = v.strip().lower()

def _tz(dt: Any):
    """Return timezone-aware UTC datetime or None."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return dt  # let Pydantic handle if string

def _to_onboarding_out(doc: Dict[str, Any]) -> OnboardingOut:
    """Map Mongo document to response schema (single validation pass)."""
    return OnboardingOut(
        id=str(doc["_id"]),
        vaping_frequency=doc.get("vaping_frequency"),
        vaping_trigger=doc.get("vaping_trigger"),
        vaping_effect=doc.get("vaping_effect"),
        hides_vaping=doc.get("hides_vaping"),
        useapp=doc.get("useapp"),  # <— NEW
        vaping_years=doc.get("vaping_years"),
        vape_cost_usd=doc.get("vape_cost_usd"),
        puff_count=doc.get("puff_count"),
        vape_lifespan_days=doc.get("vape_lifespan_days"),
        quit_attempts=doc.get("quit_attempts"),
        referral_source=doc.get("referral_source"),
        first_name=doc.get("first_name"),
        gender=doc.get("gender"),
        age=doc.get("age"),
        created_at=_tz(doc.get("created_at")),
        updated_at=_tz(doc.get("updated_at")),
    )

# -------------------------
# Controllers
# -------------------------

async def create_onboarding(payload: OnboardingRequest) -> OnboardingResponse:
    """
    Create an onboarding document (no user_id stored) and return its _id.
    """
    to_insert: Dict[str, Any] = payload.model_dump(exclude_unset=True)
    _normalize_enums(to_insert)
    to_insert["created_at"] = datetime.now(timezone.utc)

    result = await onboarding_collection.insert_one(to_insert)
    return OnboardingResponse(onboarding_id=str(result.inserted_id))

async def get_onboarding(onboarding_id: str) -> OnboardingOut:
    """
    Fetch an onboarding document by its id.
    """
    _id = _validate_object_id(onboarding_id)

    doc = await onboarding_collection.find_one({"_id": _id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding not found",
        )

    return _to_onboarding_out(doc)

async def update_onboarding(onboarding_id: str, payload: OnboardingRequest) -> OnboardingOut:
    """
    Update fields on an onboarding document; sets updated_at and returns the updated doc.
    """
    _id = _validate_object_id(onboarding_id)

    updates: Dict[str, Any] = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    _normalize_enums(updates)
    updates["updated_at"] = datetime.now(timezone.utc)

    doc = await onboarding_collection.find_one_and_update(
        {"_id": _id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding not found",
        )

    return _to_onboarding_out(doc)
