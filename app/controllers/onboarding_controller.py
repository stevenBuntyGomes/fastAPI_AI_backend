# app/controllers/onboarding_controller.py

from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from pymongo import ReturnDocument

from ..db.mongo import onboarding_collection
from ..schemas.onboarding_schema import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingOut,
)
from ..models.onboarding_model import OnboardingModel


def _validate_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid onboarding id",
        )


def _to_onboarding_out(doc: dict) -> OnboardingOut:
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


async def create_onboarding(payload: OnboardingRequest) -> OnboardingResponse:
    """
    Create an onboarding document (no user_id stored) and return its _id.
    """
    data = OnboardingModel(**payload.model_dump(exclude_unset=True))
    to_insert = data.model_dump(by_alias=True, exclude_none=True)
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

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    updates["updated_at"] = datetime.utcnow()

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
