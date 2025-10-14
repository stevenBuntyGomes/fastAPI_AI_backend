# app/routes/safety.py
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..db.mongo import (
    users_collection,
    community_collection,
    reports_collection,
    blocks_collection,
    moderation_logs,
)
from ..utils.auth_utils import (
    get_current_user,
    get_current_admin_user,
    get_moderation_admin_user,
)

router = APIRouter(prefix="/safety", tags=["Safety"])


# -----------------------------
# Helpers
# -----------------------------
def _oid(s: str) -> ObjectId:
    if not ObjectId.is_valid(s):
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    return ObjectId(s)


async def _find_comment_parent_and_author(comment_id: str) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (parent_post_id, comment_author_id) for the given comment id, if found.
    Assumes a post doc shape that contains: comments: [{ id, comment_author_id, ... }]
    """
    doc = await community_collection.find_one(
        {"comments.id": comment_id},
        projection={"_id": 1, "comments.$": 1},
    )
    if not doc:
        return None, None
    comments = doc.get("comments", [])
    if not comments:
        return str(doc["_id"]), None
    c = comments[0]
    return str(doc["_id"]), c.get("comment_author_id")


async def _auto_hide(content_id: str, content_type: str):
    if content_type == "post":
        # Hide post
        try:
            await community_collection.update_one(
                {"_id": _oid(content_id)},
                {"$set": {"status": "hidden", "hidden_reason": "reported"}},
            )
        except HTTPException:
            # If it's not a valid ObjectId, ignore (defensive)
            pass
    elif content_type == "comment":
        # Hide comment inside its parent post
        await community_collection.update_one(
            {"comments.id": content_id},
            {"$set": {
                "comments.$.status": "hidden",
                "comments.$.hidden_reason": "reported"
            }},
        )
    elif content_type == "user":
        # Soft-flag user; actual banning/suspension is separate
        try:
            await users_collection.update_one(
                {"_id": _oid(content_id)},
                {"$set": {"is_flagged": True, "flagged_at": datetime.utcnow()}},
            )
        except HTTPException:
            pass


# -----------------------------
# Schemas
# -----------------------------
class ReportCreate(BaseModel):
    content_id: str
    content_type: Literal["user", "post", "comment"]
    reason: str
    details: Optional[str] = None


class BlockRequest(BaseModel):
    target_user_id: str


class RemoveFlagRequest(BaseModel):
    content_id: str
    content_type: Literal["user", "post", "comment"]


# -----------------------------
# Public (authenticated) routes
# -----------------------------
@router.post("/reports")
async def create_report(payload: ReportCreate, user=Depends(get_current_user)):
    """
    Single universal report endpoint.
    We enrich and store:
      - target_user_id (user who owns the content being reported)
      - parent_post_id (for comments)
    """
    target_user_id: Optional[str] = None
    parent_post_id: Optional[str] = None

    if payload.content_type == "user":
        # Directly reporting a user profile
        target_user_id = payload.content_id

    elif payload.content_type == "post":
        # Find the post to get its author
        try:
            post = await community_collection.find_one({"_id": _oid(payload.content_id)})
            if post:
                target_user_id = str(post.get("post_author_id") or post.get("author_id") or "")
        except HTTPException:
            # If invalid _id or not found, leave target_user_id None
            pass

    elif payload.content_type == "comment":
        # Find comment's parent post and the comment author
        parent_post_id, comment_author_id = await _find_comment_parent_and_author(payload.content_id)
        target_user_id = comment_author_id

    doc = {
        "reporter_id": str(user["_id"]),
        "content_id": payload.content_id,
        "content_type": payload.content_type,
        "target_user_id": target_user_id,   # derived for dashboards
        "parent_post_id": parent_post_id,   # derived for comment rows
        "reason": payload.reason,
        "details": payload.details,
        "status": "open",                   # open | resolved | dismissed
        "created_at": datetime.utcnow(),
        "resolved_at": None,
        "action_taken": "auto_hidden" if payload.content_type in ("post", "comment") else None,
    }

    await reports_collection.insert_one(doc)
    await _auto_hide(payload.content_id, payload.content_type)

    return {"ok": True}


@router.post("/block")
async def block_user(payload: BlockRequest, user=Depends(get_current_user)):
    await blocks_collection.update_one(
        {"user_id": str(user["_id"])},
        {"$addToSet": {"blocked": payload.target_user_id}},
        upsert=True,
    )
    return {"ok": True}


@router.post("/unblock")
async def unblock_user(payload: BlockRequest, user=Depends(get_current_user)):
    await blocks_collection.update_one(
        {"user_id": str(user["_id"])},
        {"$pull": {"blocked": payload.target_user_id}},
    )
    return {"ok": True}


# -----------------------------
# Admin dashboard endpoints
# -----------------------------
@router.get("/admin/flagged/users")
async def list_flagged_users(admin=Depends(get_moderation_admin_user)):
    """
    Returns one row per user who has open reports (any content type),
    aggregating reasons and counts.
    """
    pipeline = [
        {"$match": {"status": "open", "target_user_id": {"$exists": True, "$ne": None}}},
        {
            "$group": {
                "_id": "$target_user_id",
                "reasons": {"$addToSet": "$reason"},
                "reports": {"$sum": 1},
                "last_report_at": {"$max": "$created_at"},
            }
        },
        {"$sort": {"last_report_at": -1}},
    ]
    rows = []
    async for r in reports_collection.aggregate(pipeline):
        rows.append({
            "user_id": r["_id"],
            "reasons": r.get("reasons", []),
            "reports": r.get("reports", 0),
            "last_report_at": r.get("last_report_at"),
        })
    return {"ok": True, "items": rows}


@router.get("/admin/flagged/posts")
async def list_flagged_posts(admin=Depends(get_moderation_admin_user)):
    """
    One row per post that has open reports.
    """
    pipeline = [
        {"$match": {"status": "open", "content_type": "post"}},
        {
            "$group": {
                "_id": "$content_id",
                "reasons": {"$addToSet": "$reason"},
                "reports": {"$sum": 1},
                "last_report_at": {"$max": "$created_at"},
                "author_id": {"$first": "$target_user_id"},
            }
        },
        {"$sort": {"last_report_at": -1}},
    ]
    rows = []
    async for r in reports_collection.aggregate(pipeline):
        rows.append({
            "post_id": r["_id"],
            "author_id": r.get("author_id"),
            "reasons": r.get("reasons", []),
            "reports": r.get("reports", 0),
            "last_report_at": r.get("last_report_at"),
        })
    return {"ok": True, "items": rows}


@router.get("/admin/flagged/comments")
async def list_flagged_comments(admin=Depends(get_moderation_admin_user)):
    """
    One row per comment that has open reports.
    Returns: comment_id, post_id, author_id, reasons, reports, last_report_at
    """
    pipeline = [
        {"$match": {"status": "open", "content_type": "comment"}},
        {
            "$group": {
                "_id": "$content_id",
                "reasons": {"$addToSet": "$reason"},
                "reports": {"$sum": 1},
                "last_report_at": {"$max": "$created_at"},
                "author_id": {"$first": "$target_user_id"},
                "post_id": {"$first": "$parent_post_id"},
            }
        },
        {"$sort": {"last_report_at": -1}},
    ]

    rows = []
    async for r in reports_collection.aggregate(pipeline):
        # Fallback: if parent_post_id/author_id were not recorded (older reports), derive now
        post_id = r.get("post_id")
        author_id = r.get("author_id")
        if not post_id or not author_id:
            # derive on the fly
            derived_post_id, derived_author_id = await _find_comment_parent_and_author(r["_id"])
            post_id = post_id or derived_post_id
            author_id = author_id or derived_author_id

        rows.append({
            "comment_id": r["_id"],
            "post_id": post_id,
            "author_id": author_id,
            "reasons": r.get("reasons", []),
            "reports": r.get("reports", 0),
            "last_report_at": r.get("last_report_at"),
        })

    return {"ok": True, "items": rows}


@router.post("/admin/remove-flag")
async def remove_flag(payload: RemoveFlagRequest, admin=Depends(get_moderation_admin_user)):
    """
    Dismiss all OPEN reports for the given item and unhide/clear flags.
    UI button label in your screenshots is 'Remove' — this implements that action.
    """
    # 1) Resolve reports
    now = datetime.utcnow()
    res = await reports_collection.update_many(
        {"status": "open", "content_type": payload.content_type, "content_id": payload.content_id},
        {"$set": {"status": "resolved", "resolved_at": now, "action_taken": "dismissed_by_admin"}},
    )

    # 2) Unhide / clear any flags
    if payload.content_type == "post":
        try:
            await community_collection.update_one(
                {"_id": _oid(payload.content_id)},
                {"$set": {"status": "active"}, "$unset": {"hidden_reason": ""}},
            )
        except HTTPException:
            pass

    elif payload.content_type == "comment":
        await community_collection.update_one(
            {"comments.id": payload.content_id},
            {"$set": {"comments.$.status": "active"}, "$unset": {"comments.$.hidden_reason": ""}},
        )

    elif payload.content_type == "user":
        try:
            await users_collection.update_one(
                {"_id": _oid(payload.content_id)},
                {"$unset": {"is_flagged": "", "flagged_at": ""}},
            )
        except HTTPException:
            pass

    # 3) Log the moderation action (optional but nice for audit)
    await moderation_logs.insert_one({
        "admin_id": str(admin["_id"]),
        "action": "remove_flag",
        "content_id": payload.content_id,
        "content_type": payload.content_type,
        "reports_updated": getattr(res, "modified_count", 0),
        "created_at": now,
    })

    return {"ok": True, "updated": getattr(res, "modified_count", 0)}
