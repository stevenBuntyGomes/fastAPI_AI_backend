from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
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
    get_moderation_admin_user,   # strict allowlist/admin guard
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
    """
    Immediate mitigation on report (Apple 1.2-friendly):
      - post: hide post
      - comment: hide comment
      - user: set is_flagged (no ban/suspend yet)
    """
    if content_type == "post":
        try:
            await community_collection.update_one(
                {"_id": _oid(content_id)},
                {"$set": {"status": "hidden", "hidden_reason": "reported"}},
            )
        except HTTPException:
            pass  # invalid id; ignore
    elif content_type == "comment":
        await community_collection.update_one(
            {"comments.id": content_id},
            {"$set": {
                "comments.$.status": "hidden",
                "comments.$.hidden_reason": "reported",
            }},
        )
    elif content_type == "user":
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


class TakedownRequest(BaseModel):
    content_id: str
    content_type: Literal["user", "post", "comment"]
    reason: Optional[str] = None  # e.g., "hate_speech", "sexual_content"


class DeleteRequest(BaseModel):
    content_id: str
    content_type: Literal["post", "comment"]  # hard delete for content only
    reason: Optional[str] = None


class BanUserRequest(BaseModel):
    user_id: str
    reason: Optional[str] = None


class SuspendUserRequest(BaseModel):
    user_id: str
    until: datetime  # (UTC) when suspension expires
    reason: Optional[str] = None


# -----------------------------
# Public (authenticated) routes
# -----------------------------
@router.post("/reports")
async def create_report(payload: ReportCreate, user=Depends(get_current_user)):
    """
    Single universal report endpoint.
    We enrich and store:
      - target_user_id (owner of content being reported)
      - parent_post_id (for comments)
    Validates existence of the target before accepting the report.
    """
    target_user_id: Optional[str] = None
    parent_post_id: Optional[str] = None

    if payload.content_type == "user":
        # ensure user exists
        try:
            user_doc = await users_collection.find_one({"_id": _oid(payload.content_id)}, projection={"_id": 1})
        except HTTPException:
            raise HTTPException(status_code=400, detail="Invalid user id")
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        target_user_id = payload.content_id

    elif payload.content_type == "post":
        # ensure post exists; derive author
        try:
            post = await community_collection.find_one(
                {"_id": _oid(payload.content_id)},
                projection={"_id": 1, "post_author_id": 1, "author_id": 1},
            )
        except HTTPException:
            raise HTTPException(status_code=400, detail="Invalid post id")
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        target_user_id = str(post.get("post_author_id") or post.get("author_id") or "")

    elif payload.content_type == "comment":
        # locate comment's parent + author
        parent_post_id, comment_author_id = await _find_comment_parent_and_author(payload.content_id)
        if not parent_post_id or not comment_author_id:
            raise HTTPException(status_code=404, detail="Comment not found")
        target_user_id = comment_author_id

    # persist report
    doc = {
        "reporter_id": str(user["_id"]),
        "content_id": payload.content_id,
        "content_type": payload.content_type,
        "target_user_id": target_user_id,   # derived
        "parent_post_id": parent_post_id,   # for comment rows
        "reason": payload.reason,
        "details": payload.details,
        "status": "open",                   # open | resolved
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


@router.get("/blocked")
async def get_blocked_users(user=Depends(get_current_user)):
    """
    Return the authenticated user's blocked list as basic user objects and count.
    Each item includes: id, name, username, avatar_url (when available).
    """
    doc = await blocks_collection.find_one(
        {"user_id": str(user["_id"])},
        projection={"_id": 0, "blocked": 1},
    )
    blocked_ids = doc.get("blocked", []) if doc else []
    if not blocked_ids:
        return {"ok": True, "items": [], "count": 0}

    # Coerce valid ObjectIds for lookup
    oid_list = [ObjectId(x) for x in blocked_ids if ObjectId.is_valid(x)]

    # Safe projection: keep it minimal and non-sensitive
    projection = {
        "_id": 1,
        "name": 1,
        "full_name": 1,          # fallback if you use this
        "display_name": 1,       # fallback if you use this
        "username": 1,
        "avatar_url": 1,
        "photo": 1,              # fallback if you use this
        "profile_picture": 1,    # fallback if you use this
    }

    items = []
    if oid_list:
        cursor = users_collection.find({"_id": {"$in": oid_list}}, projection=projection)
        async for u in cursor:
            name = u.get("name") or u.get("full_name") or u.get("display_name")
            avatar = u.get("avatar_url") or u.get("photo") or u.get("profile_picture")
            items.append({
                "id": str(u["_id"]),
                "name": name,
                "username": u.get("username"),
                "avatar_url": avatar,
            })

    # Note: if some blocked IDs are invalid/missing, they simply won’t appear in items.
    return {"ok": True, "items": items, "count": len(items)}


@router.get("/blocked/count")
async def get_blocked_users_count(user=Depends(get_current_user)):
    """
    Return only the count of blocked users for the authenticated user.
    """
    doc = await blocks_collection.find_one(
        {"user_id": str(user["_id"])},
        projection={"_id": 0, "blocked": 1},
    )
    blocked = doc.get("blocked", []) if doc else []
    return {"ok": True, "count": len(blocked)}


# -----------------------------
# Admin dashboard endpoints (strict guard)
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
        post_id = r.get("post_id")
        author_id = r.get("author_id")
        if not post_id or not author_id:
            # derive on the fly for legacy records
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
    """
    now = datetime.utcnow()

    # Close reports
    res = await reports_collection.update_many(
        {"status": "open", "content_type": payload.content_type, "content_id": payload.content_id},
        {"$set": {"status": "resolved", "resolved_at": now, "action_taken": "dismissed_by_admin"}},
    )

    # Unhide / clear flags
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

    await moderation_logs.insert_one({
        "admin_id": str(admin["_id"]),
        "action": "remove_flag",
        "content_id": payload.content_id,
        "content_type": payload.content_type,
        "reports_updated": getattr(res, "modified_count", 0),
        "created_at": now,
    })

    return {"ok": True, "updated": getattr(res, "modified_count", 0)}


@router.post("/admin/takedown")
async def takedown(payload: TakedownRequest, admin=Depends(get_moderation_admin_user)):
    """
    Soft-remove violating content (or ban a user) and resolve reports.
      - post: status=removed (kept in DB for audit)
      - comment: comments.$.status=removed
      - user: is_banned=true
    """
    now = datetime.utcnow()
    updated = 0
    reason = payload.reason or "policy_violation"

    if payload.content_type == "post":
        post_res = await community_collection.update_one(
            {"_id": _oid(payload.content_id)},
            {"$set": {
                "status": "removed",
                "removed_reason": reason,
                "removed_at": now,
                "removed_by": str(admin["_id"]),
            }}
        )
        if post_res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")
        updated += post_res.modified_count

    elif payload.content_type == "comment":
        cm_res = await community_collection.update_one(
            {"comments.id": payload.content_id},
            {"$set": {
                "comments.$.status": "removed",
                "comments.$.removed_reason": reason,
                "comments.$.removed_at": now,
                "comments.$.removed_by": str(admin["_id"]),
            }}
        )
        if cm_res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Comment not found")
        updated += cm_res.modified_count

    elif payload.content_type == "user":
        ures = await users_collection.update_one(
            {"_id": _oid(payload.content_id)},
            {"$set": {
                "is_banned": True,
                "banned_at": now,
                "banned_by": str(admin["_id"]),
                "ban_reason": reason,
            }}
        )
        if ures.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        updated += ures.modified_count

    rep_res = await reports_collection.update_many(
        {"status": "open", "content_id": payload.content_id, "content_type": payload.content_type},
        {"$set": {"status": "resolved", "resolved_at": now, "action_taken": "takedown", "action_reason": reason}}
    )

    await moderation_logs.insert_one({
        "admin_id": str(admin["_id"]),
        "action": "takedown",
        "content_id": payload.content_id,
        "content_type": payload.content_type,
        "reason": reason,
        "reports_resolved": getattr(rep_res, "modified_count", 0),
        "created_at": now,
    })

    return {"ok": True, "updated": updated, "reports_resolved": getattr(rep_res, "modified_count", 0)}


@router.post("/admin/delete")
async def hard_delete(payload: DeleteRequest, admin=Depends(get_moderation_admin_user)):
    """
    Hard delete content from the database (post or comment).
    For users, prefer ban/suspend; hard-delete users is not supported here.
    """
    now = datetime.utcnow()
    deleted = 0

    if payload.content_type == "post":
        del_res = await community_collection.delete_one({"_id": _oid(payload.content_id)})
        if del_res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")
        deleted += del_res.deleted_count

    elif payload.content_type == "comment":
        del_res = await community_collection.update_one(
            {"comments.id": payload.content_id},
            {"$pull": {"comments": {"id": payload.content_id}}}
        )
        if del_res.matched_count == 0 or del_res.modified_count == 0:
            raise HTTPException(status_code=404, detail="Comment not found")
        deleted += del_res.modified_count

    else:
        raise HTTPException(status_code=400, detail="Hard delete supports only 'post' or 'comment'.")

    rep_res = await reports_collection.update_many(
        {"status": "open", "content_id": payload.content_id, "content_type": payload.content_type},
        {"$set": {"status": "resolved", "resolved_at": now, "action_taken": "hard_delete", "action_reason": payload.reason}}
    )

    await moderation_logs.insert_one({
        "admin_id": str(admin["_id"]),
        "action": "hard_delete",
        "content_id": payload.content_id,
        "content_type": payload.content_type,
        "reason": payload.reason,
        "reports_resolved": getattr(rep_res, "modified_count", 0),
        "created_at": now,
    })

    return {"ok": True, "deleted": deleted, "reports_resolved": getattr(rep_res, "modified_count", 0)}


@router.post("/admin/ban-user")
async def ban_user(payload: BanUserRequest, admin=Depends(get_moderation_admin_user)):
    now = datetime.utcnow()
    ures = await users_collection.update_one(
        {"_id": _oid(payload.user_id)},
        {"$set": {
            "is_banned": True,
            "banned_at": now,
            "banned_by": str(admin["_id"]),
            "ban_reason": payload.reason or "policy_violation",
        }}
    )
    if ures.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    await moderation_logs.insert_one({
        "admin_id": str(admin["_id"]),
        "action": "ban_user",
        "user_id": payload.user_id,
        "reason": payload.reason,
        "created_at": now,
    })
    return {"ok": True}


@router.post("/admin/suspend-user")
async def suspend_user(payload: SuspendUserRequest, admin=Depends(get_moderation_admin_user)):
    now = datetime.utcnow()
    if payload.until <= now:
        raise HTTPException(status_code=400, detail="'until' must be in the future")

    ures = await users_collection.update_one(
        {"_id": _oid(payload.user_id)},
        {"$set": {
            "is_suspended": True,
            "suspended_until": payload.until,
            "suspended_by": str(admin["_id"]),
            "suspend_reason": payload.reason or "policy_violation",
        }}
    )
    if ures.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    await moderation_logs.insert_one({
        "admin_id": str(admin["_id"]),
        "action": "suspend_user",
        "user_id": payload.user_id,
        "until": payload.until,
        "reason": payload.reason,
        "created_at": now,
    })
    return {"ok": True}
