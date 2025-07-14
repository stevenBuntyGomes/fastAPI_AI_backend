from fastapi import APIRouter, Depends, HTTPException
from ..schemas.recovery_schema import RecoveryCreateRequest, RecoveryResponse
from ..controllers import recovery_controller
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/recovery", tags=["Recovery"])

# 🚀 Create recovery data
@router.post("/", response_model=RecoveryResponse)
async def create_recovery(
    recovery_data: RecoveryCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    return await recovery_controller.create_recovery(current_user, recovery_data)


# 🔍 Get logged-in user's recovery data
@router.get("/", response_model=RecoveryResponse)
async def get_recovery(current_user: dict = Depends(get_current_user)):
    return await recovery_controller.get_recovery_by_user(current_user)


# 🔁 Update recovery data
@router.put("/", response_model=RecoveryResponse)
async def update_recovery(
    recovery_data: RecoveryCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    return await recovery_controller.update_recovery(current_user, recovery_data)
