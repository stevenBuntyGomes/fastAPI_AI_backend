# app/routes/friend.py
from fastapi import APIRouter, Depends
from typing import List
from ..schemas.friend import (
    FriendCreate, FriendResponse, FriendUpdate,
    FriendRequestSend, FriendRequestAct, FriendRequestListQuery, FriendRequestResponse,
    UnfriendRequest
)
from ..controllers.friend_controller import (
    create_friend_profile,
    get_all_friend_profiles,
    get_friend_profile_by_id,
    update_friend_profile,
    delete_friend_profile,
    send_friend_request,
    accept_friend_request,
    reject_friend_request,
    cancel_friend_request,
    list_friend_requests,
    unfriend,
)
from ..utils.auth_utils import get_current_user

router = APIRouter(prefix="/friend", tags=["Friend Profile"])

# ---------- Friend Requests (STATIC PATHS FIRST) ----------
@router.post("/request/send", response_model=FriendRequestResponse, summary="Send a friend request")
async def send_request_route(
    data: FriendRequestSend,
    user: dict = Depends(get_current_user)
):
    return await send_friend_request(user, data)

@router.post("/request/accept", response_model=FriendRequestResponse, summary="Accept a friend request")
async def accept_request_route(
    data: FriendRequestAct,
    user: dict = Depends(get_current_user)
):
    return await accept_friend_request(user, data)

@router.post("/request/reject", response_model=FriendRequestResponse, summary="Reject a friend request")
async def reject_request_route(
    data: FriendRequestAct,
    user: dict = Depends(get_current_user)
):
    return await reject_friend_request(user, data)

@router.post("/request/cancel", response_model=FriendRequestResponse, summary="Cancel my pending request")
async def cancel_request_route(
    data: FriendRequestAct,
    user: dict = Depends(get_current_user)
):
    return await cancel_friend_request(user, data)

@router.get("/requests", response_model=List[FriendRequestResponse], summary="List my friend requests")
async def list_requests_route(
    status: str | None = None,
    role: str | None = "all",
    skip: int = 0,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    query = FriendRequestListQuery(status=status, role=role, skip=skip, limit=limit)
    return await list_friend_requests(user, query)

# ---------- Unfriend (static path) ----------
@router.post("/unfriend", summary="Remove friendship both ways")
async def unfriend_route(
    data: UnfriendRequest,
    user: dict = Depends(get_current_user)
):
    return await unfriend(user, data)

# ---------- Friend Profile (dynamic paths later) ----------
@router.post("/", response_model=FriendResponse)
async def create_friend_route(
    data: FriendCreate,
    user: dict = Depends(get_current_user)
):
    return await create_friend_profile(user, data)

@router.get("/", response_model=List[FriendResponse])
async def get_all_friends_route(user: dict = Depends(get_current_user)):
    return await get_all_friend_profiles()  # or get_friend_profiles(user) if you only want self

@router.get("/{friend_id}", response_model=FriendResponse)
async def get_friend_by_id_route(
    friend_id: str,
    user: dict = Depends(get_current_user)
):
    return await get_friend_profile_by_id(friend_id, user)

@router.put("/{friend_id}", response_model=FriendResponse)
async def update_friend_route(
    friend_id: str,
    data: FriendUpdate,
    user: dict = Depends(get_current_user)
):
    return await update_friend_profile(friend_id, data, user)

@router.delete("/{friend_id}")
async def delete_friend_route(
    friend_id: str,
    user: dict = Depends(get_current_user)
):
    return await delete_friend_profile(friend_id, user)
