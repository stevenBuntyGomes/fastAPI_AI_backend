from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.schemas.community_schema import (
    PostCreateRequest,
    PostResponse,
    CommentCreateRequest,
    PostUpdateRequest,
    CommentSchema
)
from app.controllers.community_controller import (
    create_post,
    get_all_posts,
    like_post,
    add_comment,
    update_post,
    delete_post,
)
from app.utils.auth_utils import get_current_user
from app.models.auth import UserModel  # ✅ corrected import

router = APIRouter(prefix="/community", tags=["Community"])


# ✅ Create a new community post
@router.post("/post", response_model=PostResponse, summary="Create a new community post")
async def create_community_post(
    post_data: PostCreateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    return await create_post(post_data, current_user)


# ✅ Get all posts
@router.get("/posts", response_model=List[PostResponse], summary="Get all community posts")
async def get_community_posts(
    current_user: UserModel = Depends(get_current_user)
):
    return await get_all_posts(current_user)


# ✅ Like a post
@router.post("/like/{post_id}", summary="Like a post by ID")
async def like_community_post(
    post_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    return await like_post(post_id, current_user)


# ✅ Add a comment

# ✅ Add a comment (returns the created comment)
@router.post("/comment/{post_id}", response_model=CommentSchema, summary="Add a comment to a post")
async def add_community_comment(
    post_id: str,
    comment_data: CommentCreateRequest,
    current_user: UserModel = Depends(get_current_user)
):
    return await add_comment(post_id, comment_data, current_user)


@router.put("/update/{post_id}")
async def update_post_route(
    post_id: str,
    data: PostUpdateRequest,
    user: dict = Depends(get_current_user)
):
    return await update_post(post_id, data, str(user["_id"]))


router.delete("/delete/{post_id}", summary="Delete a post")
async def delete_post_route(
    post_id: str,
    user: dict = Depends(get_current_user)
):
    return await delete_post(post_id, str(user["_id"]))
