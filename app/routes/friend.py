from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ..schemas.friend import FriendCreate, FriendResponse, FriendUpdate
from ..controllers.friend_controller import (
    create_friend_profile,
    get_all_friend_profiles,
    get_friend_profile_by_id,
    update_friend_profile,
    delete_friend_profile
)
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/friend", tags=["Friend Profile"])


# ✅ Create Friend Profile
@router.post("/", response_model=FriendResponse)
async def create_friend_route(
    data: FriendCreate,
    user=Depends(get_current_user)
):
    return await create_friend_profile(user, data)


# ✅ Get All Friend Profiles for Authenticated User
@router.get("/", response_model=List[FriendResponse])
async def get_all_friends_route(user=Depends(get_current_user)):
    return await get_all_friend_profiles(user)


# ✅ Get One Friend by ID
@router.get("/{friend_id}", response_model=FriendResponse)
async def get_friend_by_id_route(friend_id: str, user=Depends(get_current_user)):
    return await get_friend_profile_by_id(user, friend_id)


# ✅ Update Friend
@router.put("/{friend_id}", response_model=FriendResponse)
async def update_friend_route(
    friend_id: str,
    data: FriendUpdate,
    user=Depends(get_current_user)
):
    return await update_friend_profile(user, friend_id, data)


# ✅ Delete Friend
@router.delete("/{friend_id}")
async def delete_friend_route(friend_id: str, user=Depends(get_current_user)):
    return await delete_friend_profile(user, friend_id)
