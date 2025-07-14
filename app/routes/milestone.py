from fastapi import APIRouter, Depends, HTTPException
from app.controllers import milestone_controller
from app.schemas.milestone_schema import MilestoneCreateRequest, MilestoneResponse
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/milestone", tags=["Milestone"])

# ✅ Create or update milestone data
@router.post("/", response_model=MilestoneResponse)
async def create_or_update_milestone(
    payload: MilestoneCreateRequest,
    user: dict = Depends(get_current_user)
):
    return await milestone_controller.create_or_update_milestone(user, payload)

# ✅ Get milestone data for current user
@router.get("/", response_model=MilestoneResponse)
async def get_user_milestone(user: dict = Depends(get_current_user)):
    return await milestone_controller.get_user_milestone(user)
