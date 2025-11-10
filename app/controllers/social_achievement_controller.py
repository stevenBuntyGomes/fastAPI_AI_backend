# app/controllers/social_achievement_controller.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from bson import ObjectId
from fastapi import HTTPException

# ---- DB collections (robust imports with fallbacks) ----
try:
    from ..db.mongo import (
        users_collection,
        community_collection,
        friend_collection,
        mypod_collection,
        social_achievements_collection,  # may not exist yet
    )
except Exception:
    # Fallback: create the collection from db if not explicitly exported
    from ..db.mongo import db, users_collection, community_collection, friend_collection, mypod_collection
    social_achievements_collection = db["social_achievements"]  # type: ignore

# Optional blocks (not required here)
try:
    from ..db.mongo import init_db_indexes
except Exception:
    init_db_indexes = None  # pragma: no cover

from ..models.social_achievement_model import SocialAchievementsModel, AchievementEntry
from ..schemas.social_achievement_schema import SocialAchievementsResponse

# ------------- helpers -------------
def _oid(v: str) -> ObjectId:
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format.")

def _now() -> datetime:
    return datetime.utcnow()

async def _ensure_indexes():
    try:
        await social_achievements_collection.create_index([("user_id", 1)], unique=True, name="unique_user")
        await social_achievements_collection.create_index([("achievements.unlocked_at", -1)], name="unlocked_at_desc")
    except Exception:
        # do not hard-fail
        pass

# Master list of achievements with targets (code -> (name, description, target or None))
ACH_DEF: Dict[str, Dict[str, Any]] = {
    "first_friend": {
        "name": "First Friend Made",
        "desc": "Unlocks after adding your first friend.",
        "target": 1,
    },
    "pod_builder": {
        "name": "Pod Builder",
        "desc": "You added 5 friends to your pod.",
        "target": 5,
    },
    "consistency_is_key": {
        "name": "Consistency is Key",
        "desc": "Sent check-ins 7 days in a row.",
        "target": 7,  # days streak
    },
    "community_spark": {
        "name": "Community Spark",
        "desc": "Posted 5 times in Community.",
        "target": 5,
    },
    "the_motivator": {
        "name": "The Motivator",
        "desc": "Left 10+ comments on others’ posts.",
        "target": 10,
    },
    "on_the_board": {
        "name": "On the Board",
        "desc": "Made it onto the Friends Leaderboard for the first time.",
        "target": 1,  # boolean-ish
    },
    "top_of_the_pod": {
        "name": "Top of the Pod",
        "desc": "Ranked #1 among friends for a full week.",
        "target": 7,  # days at #1
    },
    "bump_buddy": {
        "name": "Bump Buddy",
        "desc": "Used the “Bump” feature 20 times.",
        "target": 20,
    },
    "check_in_champion": {
        "name": "Check-In Champion",
        "desc": "Received 10+ “Check-In Nudges.”",
        "target": 10,
    },
    "first_motivation_hit": {
        "name": "First Motivation Hit Sent",
        "desc": "You boosted a friend when they needed it most.",
        "target": 1,
    },
    "pod_mvp": {
        "name": "Pod MVP",
        "desc": "Triggered 3+ different social milestones in one week.",
        "target": 3,  # unlocked count in 7d window
    },
    "silent_strength": {
        "name": "Silent Strength",
        "desc": "3+ days login streak without posting but kept bumping/checking in.",
        "target": 3,  # days
    },
    # Referral track (Lives Saved)
    "refer_1": {"name": "Lives Saved I", "desc": "Referred 1 friend.", "target": 1},
    "refer_2": {"name": "Lives Saved II", "desc": "Referred 2 friends.", "target": 2},
    "refer_3": {"name": "Lives Saved III", "desc": "Referred 3 friends.", "target": 3},
}

def _entry(code: str, unlocked: bool = False, progress: float = 0.0, progress_value: int = 0, target: Optional[int] = None, unlocked_at: Optional[datetime] = None) -> AchievementEntry:
    d = ACH_DEF[code]
    return AchievementEntry(
        code=code,
        name=d["name"],
        description=d["desc"],
        unlocked=unlocked,
        unlocked_at=unlocked_at,
        progress=round(float(progress), 2) if progress is not None else None,
        progress_value=progress_value,
        progress_target=target,
    )

async def _get_or_create_doc(user_id: str) -> dict:
    await _ensure_indexes()
    u = await social_achievements_collection.find_one({"user_id": str(user_id)})
    if u:
        return u
    payload = SocialAchievementsModel(
        user_id=str(user_id),
        achievements={},
        meta={}
    ).model_dump(by_alias=True)
    await social_achievements_collection.insert_one(payload)
    doc = await social_achievements_collection.find_one({"user_id": str(user_id)})
    return doc or payload

# ------------- metrics aggregation -------------
async def _metrics(user_id: str) -> Dict[str, Any]:
    uid = str(user_id)
    now = _now()
    day_ago = now - timedelta(days=1)
    three_days_ago = now - timedelta(days=3)
    seven_days_ago = now - timedelta(days=7)

    # friends count (prefer friend_collection; fallback to mypod.friends_list)
    friends_count = 0
    friend_doc = await friend_collection.find_one({"user_id": uid})
    if friend_doc:
        friends_count = len(friend_doc.get("friends_list", []) or [])
    else:
        mp = await mypod_collection.find_one({"user_id": ObjectId(uid)}) or await mypod_collection.find_one({"user_id": uid})
        if mp:
            friends_count = len(mp.get("friends_list", []) or [])

    # community stats
    posts_count = await community_collection.count_documents({"post_author_id": uid})
    # comments authored by user across all posts
    comments_count = 0
    # Streaming through posts is simpler/robust without agg dependencies
    async for post in community_collection.find(
        {"comments.comment_author_id": {"$exists": True}},
        {"comments": 1}
    ):
        for c in (post.get("comments") or []):
            if str(c.get("comment_author_id")) == uid:
                comments_count += 1

    # mypod & leaderboard
    mpod = await mypod_collection.find_one({"user_id": ObjectId(uid)}) or await mypod_collection.find_one({"user_id": uid})
    rank = None
    leaderboard_len = 0
    bump_total = 0
    bumps_last_3d = 0
    if mpod:
        rank = mpod.get("rank")
        leaderboard_len = len(mpod.get("friends_list") or [])
        # bump_history: count total and 3-day window
        for b in (mpod.get("bump_history") or []):
            ts = b.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    ts = None
            if ts is None:
                ts = now  # treat missing as now
            bump_total += 1
            if ts >= three_days_ago:
                bumps_last_3d += 1

    # check-in nudges & motivation hits
    nudges_total = 0
    nudges_last_3d = 0
    motivation_total = 0
    motivation_last_3d = 0
    backup_req_last_7d = 0

    if friend_doc:
        for n in (friend_doc.get("check_in_nudges") or []):
            ts = n.get("timestamp") or n.get("time") or n.get("created_at")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    ts = None
            if ts is None:
                ts = now
            nudges_total += 1
            if ts >= three_days_ago:
                nudges_last_3d += 1

        for m in (friend_doc.get("motivation_hits") or []):
            ts = m.get("timestamp") or m.get("time") or m.get("created_at")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    ts = None
            if ts is None:
                ts = now
            motivation_total += 1
            if ts >= three_days_ago:
                motivation_last_3d += 1

        for br in (friend_doc.get("backup_requests") or []):
            ts = br.get("timestamp") or br.get("created_at")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    ts = None
            if ts is None:
                ts = now
            if ts >= (now - timedelta(days=7)):
                backup_req_last_7d += 1

    # login streak & recent posting
    user = await users_collection.find_one({"_id": ObjectId(uid)})
    login_streak = int(user.get("login_streak") or 0) if user else 0

    posts_last_3d = await community_collection.count_documents({
        "post_author_id": uid,
        "post_timestamp": {"$gte": three_days_ago}
    })

    # referrals: count users with referred_by = uid
    referrals = await users_collection.count_documents({"referred_by": uid})

    return {
        "friends_count": friends_count,
        "posts_count": posts_count,
        "comments_count": comments_count,
        "rank": rank,
        "leaderboard_len": leaderboard_len,
        "bump_total": bump_total,
        "bumps_last_3d": bumps_last_3d,
        "nudges_total": nudges_total,
        "nudges_last_3d": nudges_last_3d,
        "motivation_total": motivation_total,
        "motivation_last_3d": motivation_last_3d,
        "backup_req_last_7d": backup_req_last_7d,
        "login_streak": login_streak,
        "posts_last_3d": posts_last_3d,
        "referrals": referrals,
        "now": now,
    }

# ------------- recompute -------------
async def recalc_social_achievements(user_id: str) -> SocialAchievementsResponse:
    uid = str(user_id)
    doc = await _get_or_create_doc(uid)
    ach = doc.get("achievements", {}) or {}
    meta = doc.get("meta", {}) or {}
    now = _now()

    m = await _metrics(uid)

    # ---- helpers to set/unset achievements ----
    def set_unlocked(code: str, unlocked_at: Optional[datetime] = None, progress_value: Optional[int] = None, target: Optional[int] = None, progress: Optional[float] = None):
        entry = _entry(code, unlocked=True, unlocked_at=unlocked_at or now, progress_value=progress_value or 0, target=target, progress=progress if progress is not None else 100.0)
        ach[code] = entry.model_dump()
    def set_progress(code: str, value: int, target: int):
        p = min(100.0, (float(value) / float(target)) * 100.0 if target else 0.0)
        entry = _entry(code, unlocked=False, progress=p, progress_value=value, target=target, unlocked_at=None)
        ach[code] = entry.model_dump()

    # 1) First Friend / Pod Builder
    if m["friends_count"] >= 1:
        set_unlocked("first_friend")
    else:
        set_progress("first_friend", m["friends_count"], ACH_DEF["first_friend"]["target"])

    if m["friends_count"] >= ACH_DEF["pod_builder"]["target"]:
        set_unlocked("pod_builder")
    else:
        set_progress("pod_builder", m["friends_count"], ACH_DEF["pod_builder"]["target"])

    # 2) Community Spark (posts >= 5)
    if m["posts_count"] >= ACH_DEF["community_spark"]["target"]:
        set_unlocked("community_spark")
    else:
        set_progress("community_spark", m["posts_count"], ACH_DEF["community_spark"]["target"])

    # 3) The Motivator (comments >= 10)
    if m["comments_count"] >= ACH_DEF["the_motivator"]["target"]:
        set_unlocked("the_motivator")
    else:
        set_progress("the_motivator", m["comments_count"], ACH_DEF["the_motivator"]["target"])

    # 4) On the Board — if rank is not None (means you appeared on leaderboard at least once)
    if m["rank"] is not None:
        set_unlocked("on_the_board")
    else:
        set_progress("on_the_board", 0, 1)

    # 5) Top of the Pod — #1 rank streak for 7 days
    rank1_since_key = "rank1_since"
    rank1_since = None
    # normalize meta timestamp
    if meta.get(rank1_since_key):
        rank1_since = meta.get(rank1_since_key)
        # incoming could be str if legacy
        if isinstance(rank1_since, str):
            try:
                rank1_since = datetime.fromisoformat(rank1_since.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                rank1_since = None

    if m["rank"] == 1:
        if not rank1_since:
            rank1_since = now
    else:
        rank1_since = None  # reset streak if not #1

    # save back to meta
    meta[rank1_since_key] = rank1_since

    # compute streak days
    streak_days = 0
    if rank1_since:
        streak_days = (now - rank1_since).days + 1  # count today
    if streak_days >= ACH_DEF["top_of_the_pod"]["target"]:
        set_unlocked("top_of_the_pod", unlocked_at=rank1_since, progress_value=streak_days, target=ACH_DEF["top_of_the_pod"]["target"], progress=100.0)
    else:
        set_progress("top_of_the_pod", streak_days, ACH_DEF["top_of_the_pod"]["target"])

    # 6) Bump Buddy — bumps >= 20
    if m["bump_total"] >= ACH_DEF["bump_buddy"]["target"]:
        set_unlocked("bump_buddy")
    else:
        set_progress("bump_buddy", m["bump_total"], ACH_DEF["bump_buddy"]["target"])

    # 7) Check-In Champion — nudges received >= 10
    if m["nudges_total"] >= ACH_DEF["check_in_champion"]["target"]:
        set_unlocked("check_in_champion")
    else:
        set_progress("check_in_champion", m["nudges_total"], ACH_DEF["check_in_champion"]["target"])

    # 8) First Motivation Hit Sent
    if m["motivation_total"] >= 1:
        set_unlocked("first_motivation_hit")
    else:
        set_progress("first_motivation_hit", m["motivation_total"], 1)

    # 9) Consistency is Key — daily check-ins 7 days in a row.
    # We approximate "check-ins" using bumps OR motivation hits OR backup requests, grouped by distinct day.
    # Build day set for last 7*2 days window and compute max run ending today.
    # For simplicity: success if there is at least one action (bump/motivation/backup) each of the last 7 days.
    # (Works with current data model and is monotonic.)
    # Compute present days from bump_history + motivation_hits + backup_requests
    days = set()
    # Already have counts in m for last windows; pull full arrays to be precise
    check_doc = friend_doc if 'friend_doc' in locals() else await friend_collection.find_one({"user_id": uid})
    mpod_full = mpod if 'mpod' in locals() else await mypod_collection.find_one({"user_id": ObjectId(uid)}) or await mypod_collection.find_one({"user_id": uid})
    def add_day(ts):
        if not ts:
            return
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                return
        days.add(ts.date())

    if mpod_full:
        for b in (mpod_full.get("bump_history") or []):
            add_day(b.get("timestamp"))

    if check_doc:
        for m2 in (check_doc.get("motivation_hits") or []):
            add_day(m2.get("timestamp") or m2.get("created_at"))
        for br2 in (check_doc.get("backup_requests") or []):
            add_day(br2.get("timestamp") or br2.get("created_at"))

    # Check last 7 consecutive days including today
    consec_ok = True
    for i in range(7):
        d = (now - timedelta(days=i)).date()
        if d not in days:
            consec_ok = False
            break

    if consec_ok:
        set_unlocked("consistency_is_key")
    else:
        # progress as count of most recent consecutive days
        longest = 0
        current = 0
        for i in range(14, -1, -1):
            d = (now - timedelta(days=i)).date()
            if d in days:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        set_progress("consistency_is_key", min(longest, 7), ACH_DEF["consistency_is_key"]["target"])

    # 10) Silent Strength — login streak >=3, no posts last 3 days, but bumps or nudges in last 3 days
    if (m["login_streak"] >= 3) and (m["posts_last_3d"] == 0) and ((m["bumps_last_3d"] > 0) or (m["nudges_last_3d"] > 0) or (m["motivation_last_3d"] > 0)):
        set_unlocked("silent_strength")
    else:
        # progress: min(login_streak/3) but zero out if posted recently and no outreach
        base = min(3, m["login_streak"])
        if m["posts_last_3d"] > 0:
            base = 0
        set_progress("silent_strength", base, ACH_DEF["silent_strength"]["target"])

    # 11) Referrals: refer_1/2/3 based on m["referrals"]
    ref_n = m["referrals"]
    for code, target in (("refer_1", 1), ("refer_2", 2), ("refer_3", 3)):
        if ref_n >= target:
            set_unlocked(code)
        else:
            set_progress(code, ref_n, target)

    # 12) Pod MVP — 3+ achievements unlocked within the last 7 days.
    # Count achievements (other than pod_mvp) with unlocked_at >= now-7d
    seven_days_ago = now - timedelta(days=7)
    recent_unlocked = 0
    for k, v in ach.items():
        if k == "pod_mvp":
            continue
        ts = v.get("unlocked_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                ts = None
        if ts and ts >= seven_days_ago:
            recent_unlocked += 1

    if recent_unlocked >= ACH_DEF["pod_mvp"]["target"]:
        set_unlocked("pod_mvp")
    else:
        set_progress("pod_mvp", recent_unlocked, ACH_DEF["pod_mvp"]["target"])

    # persist
    await social_achievements_collection.update_one(
        {"_id": doc.get("_id")},
        {"$set": {"achievements": ach, "meta": meta, "updated_at": now}},
        upsert=True
    )

    saved = await social_achievements_collection.find_one({"user_id": uid})
    # shape response
    public = {
        "user_id": uid,
        "achievements": {k: {
            "code": k,
            "name": v.get("name"),
            "description": v.get("description"),
            "unlocked": bool(v.get("unlocked")),
            "unlocked_at": v.get("unlocked_at"),
            "progress": float(v.get("progress") or 0.0),
            "progress_value": int(v.get("progress_value") or 0),
            "progress_target": v.get("progress_target"),
        } for k, v in (saved.get("achievements") or {}).items()},
        "updated_at": saved.get("updated_at"),
    }
    return SocialAchievementsResponse(**public)
