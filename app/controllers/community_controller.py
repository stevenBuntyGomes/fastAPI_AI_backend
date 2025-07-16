from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongo import community_collection
from app.models.auth import UserModel
from app.schemas.community_schema import (
    PostCreateRequest,
    PostResponse,
    CommentCreateRequest,
    PostUpdateRequest,
)


# ✅ Create a new post
async def create_post(post_data: PostCreateRequest, current_user: UserModel) -> PostResponse:
    post = {
        "post_text": post_data.post_text,
        "post_author_id": str(current_user.id),
        "post_visibility": post_data.post_visibility,
        "post_timestamp": datetime.utcnow(),
        "likes_count": 0,
        "liked_by": [],
        "comments": [],
    }

    result = await community_collection.insert_one(post)
    post["id"] = str(result.inserted_id)
    return PostResponse(**post)


# ✅ Get all posts
async def get_all_posts(current_user: UserModel) -> List[PostResponse]:
    posts_cursor = community_collection.find(
        {"post_visibility": {"$in": ["community", "friends_only"]}}
    ).sort("post_timestamp", -1)

    posts = []
    async for post in posts_cursor:
        post["id"] = str(post["_id"])
        posts.append(PostResponse(**post))

    return posts


# ✅ Like a post
async def like_post(post_id: str, current_user: UserModel):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    post = await community_collection.find_one({"_id": ObjectId(post_id)})

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user_id_str = str(current_user.id)

    if user_id_str in post.get("liked_by", []):
        raise HTTPException(status_code=400, detail="Already liked")

    await community_collection.update_one(
        {"_id": ObjectId(post_id)},
        {
            "$inc": {"likes_count": 1},
            "$addToSet": {"liked_by": user_id_str}
        }
    )

    return {"message": "Post liked successfully"}


from app.schemas.community_schema import CommentSchema  # ✅ make sure this is imported at the top

# ✅ Add a comment and return the comment as a validated CommentSchema
async def add_comment(post_id: str, comment_data: CommentCreateRequest, current_user: UserModel) -> CommentSchema:
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    # Build the comment
    comment = {
        "comment_text": comment_data.comment_text,
        "comment_author_id": str(current_user.id),
        "comment_timestamp": datetime.utcnow()
    }

    # Push the comment into the post
    result = await community_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$push": {"comments": comment}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")

    # Return the added comment as a validated schema
    return CommentSchema(**comment)


# ✅ Update post
async def update_post(post_id: str, data: PostUpdateRequest, user_id: str):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    existing_post = await community_collection.find_one({"_id": ObjectId(post_id)})

    if not existing_post:
        raise HTTPException(status_code=404, detail="Post not found")

    if str(existing_post["post_author_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this post")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    result = await community_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Post not updated")

    return {"message": "Post updated successfully"}


# ✅ Delete post
async def delete_post(post_id: str, user_id: str):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    post = await community_collection.find_one({"_id": ObjectId(post_id)})

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if str(post["post_author_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    await community_collection.delete_one({"_id": ObjectId(post_id)})

    return {"message": "Post deleted successfully"}
