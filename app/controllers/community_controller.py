from datetime import datetime
from typing import List
from bson import ObjectId
from fastapi import HTTPException, status
import random

from ..db.mongo import community_collection, users_collection
from ..schemas.community_schema import (
    PostCreateRequest,
    PostResponse,
    CommentCreateRequest,
    PostUpdateRequest,
    CommentSchema,
)

# 🔁 Helper: Increment user aura by 1
async def increment_user_aura(user_id: str):
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"aura": 1}}
    )

async def decrement_user_aura(user_id: str):
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"aura": -1}}
    )

async def generate_comment_id(user_id: str) -> str:
    random_part = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{user_id}_{random_part}"

# ✅ Create a new post
async def create_post(post_data: PostCreateRequest, current_user: dict) -> PostResponse:
    post = {
        "post_text": post_data.post_text,
        "post_author_id": str(current_user["_id"]),
        "post_visibility": post_data.post_visibility,
        "post_timestamp": datetime.utcnow(),
        "likes_count": 0,
        "liked_by": [],
        "comments": [],
    }

    result = await community_collection.insert_one(post)
    post["id"] = str(result.inserted_id)

    # 🔼 Increase aura for post creation
    await increment_user_aura(str(current_user["_id"]))

    return PostResponse(**post)


async def remove_post_by_id(post_id: str, current_user: dict):
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="❌ Invalid post ID")

    post = await community_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="❌ Post not found")

    if str(post["post_author_id"]) != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="❌ Not authorized to delete this post")

    await community_collection.delete_one({"_id": ObjectId(post_id)})

    # Optional: Decrement aura if needed
    await decrement_user_aura(str(current_user["_id"]))

    return {"message": "✅ Post deleted successfully"}



# ✅ Get all posts
from ..models.auth import UserModel  # Ensure this has necessary fields like name, profile_picture

# ✅ Get all posts with comment author populated
async def get_all_posts(current_user: dict, skip: int = 0, limit: int = 6) -> List[PostResponse]:
    posts_cursor = community_collection.find(
        {"post_visibility": {"$in": ["community", "friends_only"]}}
    ).sort("post_timestamp", -1).skip(skip).limit(limit)

    posts = []
    async for post in posts_cursor:
        post["id"] = str(post["_id"])

        # 🔍 Add post author details
        post_author = await users_collection.find_one({"_id": ObjectId(post["post_author_id"])})
        post["author"] = (
            {
                "id": str(post_author["_id"]),
                "name": post_author.get("name"),
                "profile_picture": post_author.get("profile_picture"),
            } if post_author else None
        )

        # 🔄 Enrich comments with author info
        enriched_comments = []
        for comment in post.get("comments", []):
            if "id" not in comment:
                comment["id"] = await generate_comment_id(comment["comment_author_id"])

            author = await users_collection.find_one({"_id": ObjectId(comment["comment_author_id"])})
            comment["author"] = (
                {
                    "id": str(author["_id"]),
                    "name": author.get("name"),
                    "profile_picture": author.get("profile_picture"),
                } if author else None
            )

            enriched_comments.append(comment)

        post["comments"] = enriched_comments
        posts.append(PostResponse(**post))

    return posts


# ✅ Like a post
async def like_post(post_id: str, current_user: dict) -> PostResponse:
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    post = await community_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user_id_str = str(current_user["_id"])
    already_liked = user_id_str in post.get("liked_by", [])

    if not already_liked:
        # ➕ Like
        await community_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$addToSet": {"liked_by": user_id_str}}
        )
        await community_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"likes_count": 1}}
        )
        await increment_user_aura(user_id_str)
    else:
        # ➖ Unlike
        await community_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$pull": {"liked_by": user_id_str}}
        )
        await community_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"likes_count": -1}}
        )
        await decrement_user_aura(user_id_str)

    # 🔄 Return updated post
    updated_post = await community_collection.find_one({"_id": ObjectId(post_id)})
    updated_post["id"] = str(updated_post["_id"])
    return PostResponse(**updated_post)



# ✅ Add a comment and return the comment as a validated CommentSchema
async def add_comment(post_id: str, comment_data: CommentCreateRequest, current_user: dict) -> PostResponse:
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    user_id = str(current_user["_id"])

    comment = {
        "id": await generate_comment_id(user_id),  # ✅ Unique comment ID
        "comment_text": comment_data.comment_text,
        "comment_author_id": user_id,
        "comment_timestamp": datetime.utcnow()
    }

    result = await community_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$push": {"comments": comment}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")

    await increment_user_aura(user_id)

    # ✅ Fetch and return updated post
    updated_post = await community_collection.find_one({"_id": ObjectId(post_id)})
    updated_post["id"] = str(updated_post["_id"])
    return PostResponse(**updated_post)


# update comment of the post
async def update_comment(post_id: str, comment_id: str, new_text: str, current_user: dict) -> PostResponse:
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    post = await community_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = post.get("comments", [])

    updated = False
    for i, comment in enumerate(comments):
        if comment.get("id") == comment_id:
            if str(comment["comment_author_id"]) != str(current_user["_id"]):
                raise HTTPException(status_code=403, detail="Not authorized to edit this comment")

            # ✅ Update comment content and timestamp
            comment["comment_text"] = new_text
            comment["comment_timestamp"] = datetime.utcnow()
            comments[i] = comment
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Comment not found")

    # ✅ Update the entire comments array in the post
    await community_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {"comments": comments}}
    )

    # ✅ Fetch and return the updated post
    updated_post = await community_collection.find_one({"_id": ObjectId(post_id)})
    updated_post["id"] = str(updated_post["_id"])
    return PostResponse(**updated_post)


async def delete_comment(post_id: str, comment_id: str, current_user: dict) -> PostResponse:
    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=400, detail="Invalid post ID")

    post = await community_collection.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = post.get("comments", [])
    updated_comments = []

    found = False
    for comment in comments:
        if comment.get("id") == comment_id:
            if str(comment["comment_author_id"]) != str(current_user["_id"]):
                raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
            found = True
            continue  # Skip (delete) this comment
        updated_comments.append(comment)

    if not found:
        raise HTTPException(status_code=404, detail="Comment not found")

    # ✅ Update comments array in DB
    await community_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {"comments": updated_comments}}
    )

    # ✅ Fetch and return updated post
    updated_post = await community_collection.find_one({"_id": ObjectId(post_id)})
    updated_post["id"] = str(updated_post["_id"])
    return PostResponse(**updated_post)


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
