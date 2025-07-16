from fastapi import APIRouter, Depends, HTTPException
from ..schemas.mypod_schema import MyPodModel
from ..controllers.mypod_controller import (
    get_mypod_by_user_id,
    create_or_update_mypod
)
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/mypod", tags=["MyPod"])


# ✅ Get MyPod Data for Authenticated User
@router.get("/", response_model=MyPodModel)
async def get_my_pod(user=Depends(get_current_user)):
    return await get_mypod_by_user_id(user["_id"])


# ✅ Create or Update MyPod Profile
@router.post("/", response_model=MyPodModel)
async def create_or_update_my_pod(data: MyPodModel, user=Depends(get_current_user)):
    return await create_or_update_mypod(user["_id"], data)
