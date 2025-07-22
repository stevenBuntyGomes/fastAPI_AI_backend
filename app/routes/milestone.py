from fastapi import APIRouter, Depends
from app.controllers import milestone_controller
from app.schemas.milestone_schema import MilestoneSchema
from app.utils.auth_utils import get_current_user
from typing import List

router = APIRouter(prefix="/milestone", tags=["Milestone"])

# 🔐 Get full static milestone catalog
@router.get("/", response_model=List[MilestoneSchema])
async def get_all_milestones(user: dict = Depends(get_current_user)):
    return await milestone_controller.get_all_milestones()