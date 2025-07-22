from fastapi import APIRouter, Depends, HTTPException, Query
from ..schemas.lung_check_schema import LungCheckCreateRequest
from ..utils.auth_utils import get_current_user
from ..controllers import lung_check_controller  # uses the new pagination controller
from bson import ObjectId
from datetime import datetime

router = APIRouter()


# ✅ Create or update the user's lung check history (bulk insert)
@router.post("/lung-check")
async def save_lung_check(
    data: LungCheckCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    return await lung_check_controller.create_lung_check(current_user, data)


# ✅ Get paginated lung check history for the current user
@router.get("/lung-check")
async def get_lung_check(
    skip: int = Query(0, description="Number of entries to skip (for pagination)", ge=0),
    limit: int = Query(7, description="Max number of entries to return", ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    return await lung_check_controller.get_user_lung_checks(current_user, skip, limit)