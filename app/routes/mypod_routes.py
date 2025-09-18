from typing import List
from fastapi import APIRouter, Depends
from ..schemas.mypod_schema import MyPodModel, FriendMeta
from ..controllers.mypod_controller import (
    get_mypod_by_user_id,
    create_or_update_mypod,
    add_friend_to_mypod,
    remove_friend_from_mypod,
    get_leaderboard,
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


# ✅ Add a friend (by target user's ObjectId) into mypod.friends_list
@router.post("/friends/{friend_user_id}", response_model=MyPodModel)
async def add_friend(friend_user_id: str, user=Depends(get_current_user)):
    return await add_friend_to_mypod(user["_id"], friend_user_id)


# ✅ Remove a friend from mypod.friends_list
@router.delete("/friends/{friend_user_id}", response_model=MyPodModel)
async def remove_friend(friend_user_id: str, user=Depends(get_current_user)):
    return await remove_friend_from_mypod(user["_id"], friend_user_id)


# ✅ Leaderboard = mypod.friends_list sorted by aura (DESC)
@router.get("/leaderboard", response_model=List[FriendMeta])
async def mypod_leaderboard(user=Depends(get_current_user)):
    return await get_leaderboard(user["_id"])
