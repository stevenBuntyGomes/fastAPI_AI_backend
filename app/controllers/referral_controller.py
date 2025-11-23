# app/controllers/referral_controller.py
import os
import random
from datetime import datetime
from bson import ObjectId
from typing import Optional, Union

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from ..db.mongo import (
    users_collection,
    referral_codes_collection,
    referrals_collection,
)
from ..models.referral_model import ReferralCodeModel, ReferralApplyModel
from ..schemas.referral_schema import (
    GenerateCodeResponse,
    ApplyReferralResponse,
    ReferralStatusResponse,
    ReferralSummaryItem,
    ReferralSummaryResponse,
    UserPreview,
)

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
REFERRAL_CODE_LEN = int(os.getenv("REFERRAL_CODE_LENGTH", "8"))
REFERRAL_DISCOUNT_CENTS = int(os.getenv("REFERRAL_DISCOUNT_CENTS", "500"))  # $5.00

# Max times a single code can be used by friends/family
MAX_REFERRAL_USES_PER_CODE = int(os.getenv("REFERRAL_MAX_USES_PER_CODE", "3"))

# Unambiguous chars: no 0/O, 1/I
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _now() -> datetime:
    # Use naive UTC datetimes (matches common patterns in your project)
    return datetime.utcnow()


def _normalize(code: str) -> str:
    return code.strip().upper()


def _oid(v) -> ObjectId:
    return v if isinstance(v, ObjectId) else ObjectId(v)


async def _get_user_preview(user_id: Union[ObjectId, str]) -> Optional[UserPreview]:
    """
    Helper to fetch basic user info by _id, accepting either ObjectId or string.
    """
    u = await users_collection.find_one({"_id": _oid(user_id)}, {"name": 1, "email": 1})
    if not u:
        return None
    return UserPreview(
        id=str(u["_id"]),
        name=u.get("name"),
        email=u.get("email"),
    )

# ──────────────────────────────────────────────────────────────────────────────
# Public controller functions
# ──────────────────────────────────────────────────────────────────────────────


async def ensure_referral_code(current_user: dict) -> GenerateCodeResponse:
    """
    Return the user's referral code, creating one if it doesn't exist.
    One code per user (enforced by unique index on user_id and code).
    """
    user_id = _oid(current_user["_id"])

    # IMPORTANT: user_id is stored as STRING in referral_codes_collection,
    # so we must query using str(user_id), not ObjectId.
    existing = await referral_codes_collection.find_one({"user_id": str(user_id)})
    if existing:
        return GenerateCodeResponse(code=existing["code"])

    # Create a unique code with a few attempts in case of collision
    for _ in range(20):
        candidate = "".join(random.choice(ALPHABET) for _ in range(REFERRAL_CODE_LEN))
        doc = ReferralCodeModel(user_id=str(user_id), code=candidate, created_at=_now())
        try:
            await referral_codes_collection.insert_one(
                doc.model_dump(by_alias=True, exclude_none=True)
            )
            return GenerateCodeResponse(code=candidate)
        except DuplicateKeyError:
            # collision on code or user_id; try again
            continue

    raise HTTPException(status_code=500, detail="Failed to generate referral code")


async def apply_referral(code: str, current_user: dict) -> ApplyReferralResponse:
    """
    Apply a referral code for the current user (referee).

    Rules:
    - Code must exist.
    - Self-referrals are blocked.
    - Each referee can apply at most ONE code (global).
    - Each referral CODE can be used at most MAX_REFERRAL_USES_PER_CODE times
      by friends/family.
    """
    referee_id = _oid(current_user["_id"])
    norm = _normalize(code)
    if not norm or len(norm) < 4:
        raise HTTPException(status_code=400, detail="Invalid referral code")

    # 1) Code must exist
    owner = await referral_codes_collection.find_one({"code": norm})
    if not owner:
        raise HTTPException(status_code=404, detail="Referral code not found")

    referrer_id: ObjectId = owner["user_id"] if isinstance(owner["user_id"], ObjectId) else _oid(owner["user_id"])

    # 2) Self-referral blocked
    if referrer_id == referee_id:
        raise HTTPException(status_code=400, detail="You cannot refer yourself")

    # 3) This referee can only apply ONE referral code in their lifetime.
    existing_for_referee = await referrals_collection.find_one(
        {"referee_user_id": str(referee_id)}
    )
    if existing_for_referee:
        ref_preview = await _get_user_preview(existing_for_referee["referrer_user_id"])
        return ApplyReferralResponse(
            applied=True,
            applied_at=existing_for_referee.get("applied_at"),
            discount_cents=int(existing_for_referee.get("discount_cents", 0)),
            referrer=ref_preview,
            message="Referral already applied",
        )

    # 4) This code can only be used MAX_REFERRAL_USES_PER_CODE times total
    usage_count = await referrals_collection.count_documents({"code": norm})
    if usage_count >= MAX_REFERRAL_USES_PER_CODE:
        raise HTTPException(
            status_code=400,
            detail=f"This referral code has already been used {MAX_REFERRAL_USES_PER_CODE} times and cannot be used again.",
        )

    # 5) Attempt to insert referral
    apply_doc = ReferralApplyModel(
        referrer_user_id=str(referrer_id),
        referee_user_id=str(referee_id),
        code=norm,
        discount_cents=REFERRAL_DISCOUNT_CENTS,
        applied_at=_now(),
    )

    try:
        await referrals_collection.insert_one(
            apply_doc.model_dump(by_alias=True, exclude_none=True)
        )
    except DuplicateKeyError:
        # In case of a race condition, re-read and respond with the existing info.
        existing = await referrals_collection.find_one({"referee_user_id": str(referee_id)})
        ref_preview = await _get_user_preview(existing["referrer_user_id"]) if existing else None
        return ApplyReferralResponse(
            applied=True,
            applied_at=existing.get("applied_at") if existing else None,
            discount_cents=int(existing.get("discount_cents", 0)) if existing else 0,
            referrer=ref_preview,
            message="Referral already applied",
        )

    # 6) Credit discount to referee wallet
    await users_collection.update_one(
        {"_id": referee_id},
        {"$inc": {"discount_credits_cents": REFERRAL_DISCOUNT_CENTS}},
        upsert=False,
    )

    ref_preview = await _get_user_preview(referrer_id)
    return ApplyReferralResponse(
        applied=True,
        applied_at=apply_doc.applied_at,
        discount_cents=REFERRAL_DISCOUNT_CENTS,
        referrer=ref_preview,
        message="Referral applied",
    )


async def get_referral_status(current_user: dict) -> ReferralStatusResponse:
    referee_id = _oid(current_user["_id"])

    # Stored as string in referrals_collection
    rec = await referrals_collection.find_one({"referee_user_id": str(referee_id)})

    # Current wallet credit (0 if missing)
    user = await users_collection.find_one({"_id": referee_id}, {"discount_credits_cents": 1})
    wallet = int(user.get("discount_credits_cents", 0)) if user else 0

    if not rec:
        return ReferralStatusResponse(
            has_applied=False,
            applied_code=None,
            applied_at=None,
            referrer=None,
            discount_cents=wallet,
        )

    ref_preview = await _get_user_preview(rec["referrer_user_id"])
    return ReferralStatusResponse(
        has_applied=True,
        applied_code=rec.get("code"),
        applied_at=rec.get("applied_at"),
        referrer=ref_preview,
        discount_cents=wallet,
    )


async def list_my_referrals(current_user: dict) -> ReferralSummaryResponse:
    """
    For a referrer: list all referees who used my code.
    """
    referrer_id = _oid(current_user["_id"])

    # Stored as string in referrals_collection
    cursor = referrals_collection.find(
        {"referrer_user_id": str(referrer_id)}
    ).sort("applied_at", -1)

    items = []
    async for r in cursor:
        prev = await _get_user_preview(r["referee_user_id"])
        if prev:
            items.append(
                ReferralSummaryItem(
                    referee=prev,
                    code=r.get("code", ""),
                    applied_at=r["applied_at"],
                )
            )

    return ReferralSummaryResponse(total=len(items), items=items)
