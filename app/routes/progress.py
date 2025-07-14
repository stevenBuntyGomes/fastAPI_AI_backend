from fastapi import APIRouter, Depends
from ..schemas.progress_schema import ProgressCreateRequest
from ..controllers import progress_controller
from ..utils.auth_utils import get_current_user  # ✅ Authenticated route
from typing import Dict

router = APIRouter()


# ✅ Save or update progress (Authenticated)
@router.post("/progress", summary="Create or update user progress")
async def save_progress(
    data: ProgressCreateRequest,
    current_user: Dict = Depends(get_current_user)
):
    return await progress_controller.save_user_progress(str(current_user["_id"]), data)


# ✅ Get user progress (Authenticated)
@router.get("/progress", summary="Get progress for logged-in user")
async def get_progress(current_user: Dict = Depends(get_current_user)):
    return await progress_controller.get_user_progress(str(current_user["_id"]))
