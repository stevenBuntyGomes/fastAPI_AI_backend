# app/controllers/community_controller.py
from __future__ import annotations

from datetime import datetime
from typing import List
from bson import ObjectId
from fastapi import HTTPException
import random

from ..db.mongo import community_collection, users_collection

# blocks_collection is optional – if it's not defined in your db module yet, we'll handle it gracefully.
try:
    from ..db.mongo import blocks_collection  # added for block-aware feeds
except Exception:  # pragma: no cover
    blocks_collection = None  # type: ignore

from ..schemas.community_schema import (
    PostCreateRequest,
    PostResponse,
    CommentCreateRequest,
    PostUpdateRequest,
    CommentSchema,
)

# 🔐 Server-side moderation (filters profanity/slurs, keeps text readable)
from ..utils.moderation import moderate_text


# ---------------------------
# Helpers
# ---------------------------

async def increment_user_aura(user_id: str):
    await users_collection.update_one({"_id": ObjectId(user_id)}, {"$inc": {"aura": 1}})


async def decrement_user_aura(user_id: str):
    await users_collection.update_one({"_id": ObjectId(user_id)}, {"$inc": {"aura": -1}})


async def generate_comment_id(user_id: str) -> str:
    random_part = "".join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{user_id}_{random_part}"


def _ensure_oid(id_str: str) -> ObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=400, detail="❌ Invalid ObjectId")
    return ObjectId(id_str)


def _post_to_response_dict(doc: dict) -> dict:
    """
    Return only the fields PostResponse expects.
    Avoid leaking extra DB fields (e.g., moderation/status) that might break Pydantic schema.
    """
    base = {
        "id": str(doc.get("_id") or doc.get("id")),
        "post_text": doc.get("post_text", ""),
        "post_author_id": str(doc.get("post_author_id")),
        "post_visibility": doc.get("post_visibility"),
        "post_timestamp": doc.get("post_timestamp"),
        "likes_count": int(doc.get("likes_count", 0)),
        "liked_by": list(doc.get("liked_by", [])),
        "comments": list(doc.get("comments", [])),
    }

    # If your PostResponse includes "author", attach it
    if "author" in doc:
        base["author"] = doc["author"]

    return base


# ---------------------------
# Create / Delete Post
# ---------------------------

async def create_post(post_data: PostCreateRequest, current_user: dict) -> PostResponse:
    # 🔎 Sanitize content before storing
    m = moderate_text(post_data.post_text, "en")
    post = {
        "post_text": m["cleaned"],
        "post_author_id": str(current_user["_id"]),
        "post_visibility": post_data.post_visibility,
        "post_timestamp": datetime.utcnow(),
        "likes_count": 0,
        "liked_by": [],
        "comments": [],
        # You can keep internal moderation fields if you want to later auto-hide or review:
        # "moderation": {"flagged": m["flagged"], "reason": m["reason"]},
        # "status": "hidden" if m["flagged"] else "visible",
    }

    result = await community_collection.insert_one(post)
    post["_id"] = result.inserted_id

    # 🔼 Increase aura for post creation
    await increment_user_aura(str(current_user["_id"]))

    return PostResponse(**_post_to_response_dict(post))


async def remove_post_by_id(post_id: str, current_user: dict):
    oid = _ensure_oid(post_id)

    post = await community_collection.find_one({"_id": oid})
    if not post:
        raise HTTPException(status_code=404, detail="❌ Post not found")

    if str(post["post_author_id"]) != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="❌ Not authorized to delete this post")

    await community_collection.delete_one({"_id": oid})

    # Optional: Decrement aura if needed
    await decrement_user_aura(str(current_user["_id"]))

    return {"message": "✅ Post deleted successfully"}


# ---------------------------
# Feed (block-aware, author/comment enrichment)
# ---------------------------

async def get_all_posts(current_user: dict, skip: int = 0, limit: int = 6) -> List[PostResponse]:
    # Determine blocked users (if feature exists)
    blocked = []
    if blocks_collection is not None:
        row = await blocks_collection.find_one({"user_id": str(current_user["_id"])}) or {}
        blocked = row.get("blocked", []) or []

    # Only fetch expected visibilities; exclude blocked authors
    query = {
        "post_visibility": {"$in": ["community", "friends_only"]},
        "post_author_id": {"$nin": blocked},
        "$or": [
            {"status": {"$exists": False}},
            {"status": "visible"},
        ],  # exclude hidden posts
    }

    cursor = (
        community_collection.find(query)
        .sort("post_timestamp", -1)
        .skip(max(0, skip))
        .limit(max(1, min(limit, 100)))
    )

    posts: List[PostResponse] = []
    async for doc in cursor:
        # 🔍 Attach author
        author = None
        try:
            author_doc = await users_collection.find_one(
                {"_id": _ensure_oid(doc["post_author_id"])}
            )
            if author_doc:
                author = {
                    "id": str(author_doc["_id"]),
                    "name": author_doc.get("name"),
                    # ✅ Use avatar_url (fallback to legacy memoji_url if present)
                    "avatar_url": author_doc.get("avatar_url") or author_doc.get("memoji_url"),
                }
        except HTTPException:
            author = None

        # 🔄 Enrich comments with author info (and keep IDs stable)
        enriched_comments = []
        for c in doc.get("comments", []):
            # Skip hidden comments if you start marking them
            if c.get("status") == "hidden":
                continue

            # Ensure each comment has a stable id
            if "id" not in c:
                c["id"] = await generate_comment_id(c.get("comment_author_id", "unknown"))

            c_author = None
            try:
                c_doc = await users_collection.find_one(
                    {"_id": _ensure_oid(c["comment_author_id"])}
                )
                if c_doc:
                    c_author = {
                        "id": str(c_doc["_id"]),
                        "name": c_doc.get("name"),
                        # ✅ Use avatar_url (fallback to memoji_url)
                        "avatar_url": c_doc.get("avatar_url") or c_doc.get("memoji_url"),
                    }
            except Exception:
                c_author = None

            c["author"] = c_author
            enriched_comments.append(c)

        # Build safe response dict
        doc_local = dict(doc)
        doc_local["comments"] = enriched_comments
        if author:
            doc_local["author"] = author

        posts.append(PostResponse(**_post_to_response_dict(doc_local)))

    return posts


# ---------------------------
# Like / Unlike
# ---------------------------

async def like_post(post_id: str, current_user: dict) -> PostResponse:
    oid = _ensure_oid(post_id)
    post = await community_collection.find_one({"_id": oid})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user_id_str = str(current_user["_id"])
    already_liked = user_id_str in post.get("liked_by", [])

    if not already_liked:
        await community_collection.update_one(
            {"_id": oid},
            {
                "$addToSet": {"liked_by": user_id_str},
                "$inc": {"likes_count": 1},
            },
        )
        await increment_user_aura(user_id_str)
    else:
        await community_collection.update_one(
            {"_id": oid},
            {
                "$pull": {"liked_by": user_id_str},
                "$inc": {"likes_count": -1},
            },
        )
        await decrement_user_aura(user_id_str)

    updated = await community_collection.find_one({"_id": oid})
    return PostResponse(**_post_to_response_dict(updated))


# ---------------------------
# Comments (add / update / delete)
# ---------------------------

async def add_comment(
    post_id: str,
    comment_data: CommentCreateRequest,
    current_user: dict,
) -> PostResponse:
    oid = _ensure_oid(post_id)
    user_id = str(current_user["_id"])

    # 🔎 Sanitize comment text
    m = moderate_text(comment_data.comment_text, "en")

    comment = {
        "id": await generate_comment_id(user_id),
        "comment_text": m["cleaned"],
        "comment_author_id": user_id,
        "comment_timestamp": datetime.utcnow(),
        # Optional internal flags:
        # "moderation": {"flagged": m["flagged"], "reason": m["reason"]},
        # "status": "hidden" if m["flagged"] else "visible",
    }

    result = await community_collection.update_one(
        {"_id": oid},
        {"$push": {"comments": comment}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")

    await increment_user_aura(user_id)

    updated = await community_collection.find_one({"_id": oid})
    return PostResponse(**_post_to_response_dict(updated))


async def update_comment(
    post_id: str,
    comment_id: str,
    new_text: str,
    current_user: dict,
) -> PostResponse:
    oid = _ensure_oid(post_id)
    post = await community_collection.find_one({"_id": oid})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = post.get("comments", [])
    updated_flag = False

    # 🔎 Sanitize new text
    m = moderate_text(new_text, "en")

    for i, c in enumerate(comments):
        if c.get("id") == comment_id:
            if str(c["comment_author_id"]) != str(current_user["_id"]):
                raise HTTPException(status_code=403, detail="Not authorized to edit this comment")

            c["comment_text"] = m["cleaned"]
            c["comment_timestamp"] = datetime.utcnow()
            # Optional internal flags:
            # c["moderation"] = {"flagged": m["flagged"], "reason": m["reason"]}
            # if m["flagged"]:
            #     c["status"] = "hidden"
            comments[i] = c
            updated_flag = True
            break

    if not updated_flag:
        raise HTTPException(status_code=404, detail="Comment not found")

    await community_collection.update_one({"_id": oid}, {"$set": {"comments": comments}})

    updated_post = await community_collection.find_one({"_id": oid})
    return PostResponse(**_post_to_response_dict(updated_post))


async def delete_comment(
    post_id: str,
    comment_id: str,
    current_user: dict,
) -> PostResponse:
    oid = _ensure_oid(post_id)
    post = await community_collection.find_one({"_id": oid})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = post.get("comments", [])
    updated_comments = []
    found = False

    for c in comments:
        if c.get("id") == comment_id:
            if str(c["comment_author_id"]) != str(current_user["_id"]):
                raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
            found = True
            continue
        updated_comments.append(c)

    if not found:
        raise HTTPException(status_code=404, detail="Comment not found")

    await community_collection.update_one(
        {"_id": oid},
        {"$set": {"comments": updated_comments}},
    )

    updated_post = await community_collection.find_one({"_id": oid})
    return PostResponse(**_post_to_response_dict(updated_post))


# ---------------------------
# Update / Delete Post
# ---------------------------

async def update_post(post_id: str, data: PostUpdateRequest, user_id: str):
    oid = _ensure_oid(post_id)
    existing_post = await community_collection.find_one({"_id": oid})
    if not existing_post:
        raise HTTPException(status_code=404, detail="Post not found")

    if str(existing_post["post_author_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this post")

    # Prepare update fields
    update_data = {}
    if data.post_text is not None:
        m = moderate_text(data.post_text, "en")
        update_data["post_text"] = m["cleaned"]
        # Optional internal flags:
        # update_data["moderation"] = {"flagged": m["flagged"], "reason": m["reason"]}
        # if m["flagged"]:
        #     update_data["status"] = "hidden"

    if data.post_visibility is not None:
        update_data["post_visibility"] = data.post_visibility

    if not update_data:
        return {"message": "No changes"}

    result = await community_collection.update_one({"_id": oid}, {"$set": update_data})
    if result.modified_count == 0:
        # Doc existed but nothing changed
        return {"message": "Post updated (no content change)"}

    return {"message": "Post updated successfully"}


async def delete_post(post_id: str, user_id: str):
    oid = _ensure_oid(post_id)
    post = await community_collection.find_one({"_id": oid})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if str(post["post_author_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    await community_collection.delete_one({"_id": oid})
    return {"message": "Post deleted successfully"}
