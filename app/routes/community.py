# app/routes/community.py
from fastapi import APIRouter, Depends
from typing import List

from app.schemas.community_schema import (
    PostCreateRequest,
    PostResponse,
    CommentCreateRequest,
    PostUpdateRequest,
    CommentSchema,
)
from app.controllers.community_controller import (
    create_post,
    remove_post_by_id,
    get_all_posts,
    like_post,
    add_comment,
    update_comment,
    delete_comment,
    update_post,
    delete_post,
)
from app.utils.auth_utils import get_current_user

router = APIRouter(prefix="/community", tags=["Community"])


# ✅ Create a new community post
@router.post("/post", response_model=PostResponse, summary="Create a new community post")
async def create_community_post(
    post_data: PostCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    return await create_post(post_data, current_user)


# ✅ Remove post by ID (entire post delete)
@router.delete("/remove/{post_id}", summary="Remove a post by ID")
async def remove_post_route(
    post_id: str,
    current_user: dict = Depends(get_current_user),
):
    return await remove_post_by_id(post_id, current_user)


# ✅ Get all posts (paginated)
@router.get(
    "/posts",
    response_model=List[PostResponse],
    summary="Get paginated community posts",
)
async def get_community_posts(
    skip: int = 0,            # ⬅️ How many posts to skip (offset)
    limit: int = 6,           # ⬅️ How many posts to return (default 6)
    current_user: dict = Depends(get_current_user),
):
    return await get_all_posts(current_user, skip, limit)


# ✅ Like a post
@router.post("/like/{post_id}", response_model=PostResponse, summary="Like a post by ID")
async def like_community_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
):
    return await like_post(post_id, current_user)


# ✅ Add a comment (returns updated post)
@router.post(
    "/comment/{post_id}",
    response_model=PostResponse,
    summary="Add a comment and return updated post",
)
async def add_community_comment(
    post_id: str,
    comment_data: CommentCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    return await add_comment(post_id, comment_data, current_user)


# ✅ Update a specific comment
@router.put(
    "/comment/{post_id}/{comment_id}",
    response_model=PostResponse,
    summary="Update a specific comment on a post and return updated post",
)
async def update_community_comment(
    post_id: str,
    comment_id: str,
    new_text: str,
    current_user: dict = Depends(get_current_user),
):
    return await update_comment(post_id, comment_id, new_text, current_user)


# ✅ Delete a specific comment
@router.delete(
    "/comment/{post_id}/{comment_id}",
    response_model=PostResponse,
    summary="Delete a specific comment from a post and return the updated post",
)
async def delete_community_comment(
    post_id: str,
    comment_id: str,
    current_user: dict = Depends(get_current_user),
):
    return await delete_comment(post_id, comment_id, current_user)


# ✅ Update a post
@router.put("/update/{post_id}", summary="Update a post")
async def update_post_route(
    post_id: str,
    data: PostUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    return await update_post(post_id, data, str(current_user["_id"]))


# ✅ Delete a post
@router.delete("/delete/{post_id}", summary="Delete a post")
async def delete_post_route(
    post_id: str,
    current_user: dict = Depends(get_current_user),
):
    return await delete_post(post_id, str(current_user["_id"]))
