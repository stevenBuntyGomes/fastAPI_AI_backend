# app/controllers/mypod_controller.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from fastapi import HTTPException

from ..db.mongo import mypod_collection, users_collection
from ..schemas.mypod_schema import MyPodModel, FriendMeta, LeaderboardEntry

# -----------------------
# Helpers
# -----------------------

def _as_oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format.")


async def _owner_username(user_doc: Optional[dict]) -> str:
    if not user_doc:
        return "user"
    name = user_doc.get("name")
    if name:
        return name
    email = user_doc.get("email")
    return (email.split("@")[0] if isinstance(email, str) and "@" in email else "user")


async def _ensure_mypod(owner_user_id: str) -> dict:
    """
    Ensure the owner has a MyPod doc. Create a minimal one if missing.
    Returns the MyPod document (as stored in Mongo).
    """
    owner_oid = _as_oid(owner_user_id)
    doc = await mypod_collection.find_one({"user_id": owner_oid})
    if doc:
        return doc

    user = await users_collection.find_one({"_id": owner_oid})
    base = {
        "user_id": owner_oid,
        "username": await _owner_username(user),
        "profile_picture": None,
        "aura": int((user or {}).get("aura", 0)),
        "login_streak": int((user or {}).get("login_streak", 0)),
        "rank": None,
        "leaderboard_data": [],
        "friends_list": [],
        "bump_history": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await mypod_collection.insert_one(base)
    return await mypod_collection.find_one({"user_id": owner_oid})


async def _friend_meta_from_user(friend_user_id: str) -> dict:
    """
    Build a FriendMeta dict from the source of truth:
    - users_collection: name/email, aura
    - mypod_collection: profile_picture (if present)
    """
    friend_oid = _as_oid(friend_user_id)

    user = await users_collection.find_one({"_id": friend_oid})
    if not user:
        raise HTTPException(status_code=404, detail="Friend user not found.")

    friend_mypod = await mypod_collection.find_one({"user_id": friend_oid}) or {}

    meta = {
        # store as ObjectId in Mongo; Pydantic model will stringify on response
        "user_id": friend_oid,
        "username": await _owner_username(user),
        "profile_picture": friend_mypod.get("profile_picture"),
        "aura": int(user.get("aura", 0)),
    }
    return meta


# -----------------------
# Public controller funcs
# -----------------------

async def get_mypod_by_user_id(user_id: str) -> MyPodModel:
    """
    Fetch MyPod for a given user. Raises 404 if not found (matches your current behavior).
    """
    doc = await mypod_collection.find_one({"user_id": _as_oid(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="MyPod data not found")
    return MyPodModel(**doc)


async def create_or_update_mypod(user_id: str, data: MyPodModel) -> MyPodModel:
    """
    Create or update a user's MyPod with provided payload.
    """
    owner_oid = _as_oid(user_id)
    existing = await mypod_collection.find_one({"user_id": owner_oid})

    payload = data.model_dump(by_alias=True, exclude_unset=True)
    payload["user_id"] = owner_oid

    if existing:
        payload["updated_at"] = datetime.utcnow()
        await mypod_collection.update_one({"user_id": owner_oid}, {"$set": payload})
    else:
        payload.setdefault("created_at", datetime.utcnow())
        payload.setdefault("updated_at", datetime.utcnow())
        await mypod_collection.insert_one(payload)

    updated = await mypod_collection.find_one({"user_id": owner_oid})
    return MyPodModel(**updated)


async def upsert_friend_in_mypod(owner_user_id: str, friend_user_id: str) -> MyPodModel:
    """
    Insert or refresh a friend's meta entry inside owner's mypod.friends_list.
    De-dupes by user_id (ObjectId). Returns the updated MyPod as model.
    """
    if owner_user_id == friend_user_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as a friend.")

    owner_oid = _as_oid(owner_user_id)
    friend_oid = _as_oid(friend_user_id)

    # Ensure owner MyPod exists
    await _ensure_mypod(owner_user_id)

    # Build latest meta for friend
    meta = await _friend_meta_from_user(friend_user_id)

    # Replace any existing entry for this friend with the fresh meta
    await mypod_collection.update_one(
        {"user_id": owner_oid},
        {"$pull": {"friends_list": {"user_id": friend_oid}}}
    )
    await mypod_collection.update_one(
        {"user_id": owner_oid},
        {
            "$push": {"friends_list": meta},
            "$set": {"updated_at": datetime.utcnow()},
        }
    )

    doc = await mypod_collection.find_one({"user_id": owner_oid})
    return MyPodModel(**doc)


async def add_friend_to_mypod(owner_user_id: str, friend_user_id: str) -> MyPodModel:
    """Convenience wrapper used by routes: add/refresh a friend in MyPod."""
    return await upsert_friend_in_mypod(owner_user_id, friend_user_id)


async def remove_friend_from_mypod(owner_user_id: str, friend_user_id: str) -> MyPodModel:
    """Remove a friend from MyPod.friends_list."""
    owner_oid = _as_oid(owner_user_id)
    friend_oid = _as_oid(friend_user_id)

    await _ensure_mypod(owner_user_id)
    await mypod_collection.update_one(
        {"user_id": owner_oid},
        {
            "$pull": {"friends_list": {"user_id": friend_oid}},
            "$set": {"updated_at": datetime.utcnow()},
        }
    )
    doc = await mypod_collection.find_one({"user_id": owner_oid})
    if not doc:
        raise HTTPException(status_code=404, detail="MyPod data not found")
    return MyPodModel(**doc)


async def get_leaderboard(owner_user_id: str) -> List[FriendMeta]:
    """
    Leaderboard = MyPod.friends_list sorted by current aura (DESC).
    We refresh aura values from users collection at read-time to keep it fresh.
    """
    owner_oid = _as_oid(owner_user_id)
    doc = await mypod_collection.find_one({"user_id": owner_oid})
    if not doc:
        raise HTTPException(status_code=404, detail="MyPod data not found")

    refreshed = []
    for entry in doc.get("friends_list", []):
        uid = entry.get("user_id")
        try:
            uid_oid = uid if isinstance(uid, ObjectId) else _as_oid(str(uid))
        except Exception:
            continue

        user = await users_collection.find_one({"_id": uid_oid}) or {}
        aura_now = int(user.get("aura", entry.get("aura", 0)))

        refreshed.append({
            "user_id": uid_oid,
            "username": entry.get("username"),
            "profile_picture": entry.get("profile_picture"),
            "aura": aura_now,
        })

    refreshed.sort(key=lambda x: x.get("aura", 0), reverse=True)
    return [FriendMeta(**item) for item in refreshed]


# --- Global leaderboard across ALL users, ranked by aura DESC ---
async def get_global_leaderboard(skip: int = 0, limit: int = 20) -> List[FriendMeta]:
    """
    Global leaderboard from all users, sorted by aura (DESC).
    Pagination: use ?skip=0&limit=20, then ?skip=20&limit=20, etc.
    """
    # sanitize inputs
    limit = max(1, min(limit, 50))
    skip = max(0, skip)

    # 1) Page through users by aura
    projection = {"name": 1, "email": 1, "aura": 1}
    cursor = (
        users_collection.find({}, projection)
        .sort([("aura", -1), ("_id", 1)])  # stable tie-breaker by _id
        .skip(skip)
        .limit(limit)
    )

    users_page = [doc async for doc in cursor]
    if not users_page:
        return []

    # 2) Batch-fetch profile pictures from MyPod (if present)
    ids = [u["_id"] for u in users_page]
    pics_cursor = mypod_collection.find(
        {"user_id": {"$in": ids}}, {"user_id": 1, "profile_picture": 1}
    )
    pic_map: Dict[Any, Optional[str]] = {}
    async for mp in pics_cursor:
        pic_map[mp["user_id"]] = mp.get("profile_picture")

    # 3) Build FriendMeta array (user_id, username, profile_picture, aura)
    out: List[FriendMeta] = []
    for u in users_page:
        username = await _owner_username(u)  # name → email prefix fallback
        out.append(
            FriendMeta(
                user_id=u["_id"],
                username=username,
                profile_picture=pic_map.get(u["_id"]),
                aura=int(u.get("aura") or 0),
            )
        )
    return out


# --- NEW: Rebuild rank & leaderboard_data for THIS user only ---
async def rebuild_rank_for_user(user_id: str, top_n: int = 20) -> int:
    """
    Recomputes the caller's local leaderboard among their friends (+ self),
    sorts by aura (DESC), writes:
      - mypod.rank
      - mypod.leaderboard_data  (top N entries)
    Returns the user's rank (1-based).
    """
    uid = str(user_id)

    # Fetch MyPod by either ObjectId or string user_id
    mp = await mypod_collection.find_one({"user_id": _as_oid(uid)})
    if not mp:
        # if missing, create a minimal pod first
        mp = await _ensure_mypod(uid)

    # Collect friend ids (handles mixed formats: str, ObjectId, { user_id })
    def _to_oid(v):
        if isinstance(v, dict) and v.get("user_id"):
            v = v["user_id"]
        try:
            return _as_oid(str(v))
        except Exception:
            return None

    friend_ids = mp.get("friends_list") or []
    oids = [oid for oid in (_to_oid(x) for x in friend_ids) if oid]

    me_oid = _as_oid(uid)
    if me_oid not in oids:
        oids.append(me_oid)

    # Pull aura + names
    cursor = users_collection.find(
        {"_id": {"$in": oids}},
        {"name": 1, "email": 1, "profile_picture": 1, "aura": 1},
    )
    docs = await cursor.to_list(length=10000)

    def _username(u: dict) -> str:
        name = (u.get("name") or "").strip()
        if name:
            return name
        em = (u.get("email") or "")
        return em.split("@")[0] if em else str(u["_id"])[-6:]

    rows = [{
        "user_id": str(u["_id"]),
        "username": _username(u),
        "profile_picture": (u.get("profile_picture") or None),
        "aura": int(u.get("aura") or 0),
    } for u in docs]

    rows.sort(key=lambda r: r["aura"], reverse=True)
    rank = next((i + 1 for i, r in enumerate(rows) if r["user_id"] == uid), 1)

    top = rows[: max(1, min(top_n, 50))]
    leaderboard = [LeaderboardEntry(**r).model_dump() for r in top]

    now = datetime.utcnow()
    await mypod_collection.update_one(
        {"_id": mp["_id"]},
        {"$set": {"rank": rank, "leaderboard_data": leaderboard, "updated_at": now}},
    )
    return rank
