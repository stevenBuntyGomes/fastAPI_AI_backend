# app/routes/social_achievement.py
from fastapi import APIRouter, Depends
from ..utils.auth_utils import get_current_user
from ..controllers.social_achievement_controller import recalc_social_achievements
from ..schemas.social_achievement_schema import SocialRecalcResponse

router = APIRouter(prefix="/achievements/social", tags=["Social Achievements"])

@router.get("/", response_model=SocialRecalcResponse, summary="Get social achievements (recalculates)")
async def get_social_achievements(user=Depends(get_current_user)):
    # We recalc on every fetch to keep it fresh without event hooks.
    return await recalc_social_achievements(str(user["_id"]))

@router.post("/recalculate", response_model=SocialRecalcResponse, summary="Force recompute social achievements now")
async def recalc_now(user=Depends(get_current_user)):
    return await recalc_social_achievements(str(user["_id"]))
