# app/db/mongo.py
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL")
if not MONGO_URL:
    raise RuntimeError("MONGODB_URL env var is not set")

client = AsyncIOMotorClient(MONGO_URL)
db = client.voice_ai

# Collections
users_collection = db["users"]
socket_sessions_collection = db["socket_sessions"]
devices_collection = db["devices"]                   # apns_token per user/platform
bumps_collection = db["bumps"]                       # persisted bump history
verification_codes_collection = db["codes"]
memory_collection = db["memory"]
progress_collection = db["progress"]
lung_check_collection = db["lung_check"]
lung_relining_collection = db["lung_relining"]
milestone_collection = db["milestone"]
recovery_collection = db["recovery"]
onboarding_collection = db["onboarding"]
community_collection = db["community"]

# Friend graph
friend_collection = db["friends"]                    # stores { user_id, friend_id, ... }
friend_requests_collection = db["friend_requests"]   # NEW: stores requests { from_user_id, to_user_id, status, ... }
mypod_collection = db["mypods"]

# Referrals
referral_codes_collection = db["referral_codes"]
referrals_collection = db["referrals"]

# Safety/moderation
reports_collection = db["reports"]
blocks_collection  = db["blocks"]
moderation_logs    = db["moderation_logs"]


# OPTIONAL but recommended: call this once at startup to ensure indexes exist.
async def init_db_indexes() -> None:
    # Users: unique email
    await users_collection.create_index("email", unique=True)
    # Users moderation lookups (optional but recommended)
    await users_collection.create_index("is_flagged")
    await users_collection.create_index("is_banned")
    await users_collection.create_index([("is_suspended", 1), ("suspended_until", -1)])

    # Map user -> sockets quickly
    await socket_sessions_collection.create_index([("user_id", 1)])
    await socket_sessions_collection.create_index([("sid", 1)], unique=True)

    # Devices
    await devices_collection.create_index(
        [("user_id", 1), ("platform", 1), ("token", 1)],
        unique=True
    )
    await devices_collection.create_index("updated_at")

    # Bumps
    await bumps_collection.create_index([("to_user_id", 1), ("created_at", -1)])
    await bumps_collection.create_index([("from_user_id", 1), ("created_at", -1)])

    # Verification codes: one code per email, auto-expire at 'expires'
    await verification_codes_collection.create_index("email", unique=True)
    # TTL index: documents expire at the exact datetime in 'expires'
    await verification_codes_collection.create_index("expires", expireAfterSeconds=0)

    # Onboarding
    await onboarding_collection.create_index("created_at")

    # Community (feed & updates)
    await community_collection.create_index([("post_timestamp", -1)])
    await community_collection.create_index([("post_author_id", 1)])
    await community_collection.create_index([("post_visibility", 1), ("status", 1), ("post_timestamp", -1)])
    await community_collection.create_index([("comments.id", 1)])

    # Reports / Blocks
    await reports_collection.create_index([("status", 1), ("created_at", -1)])
    await reports_collection.create_index([("content_id", 1), ("content_type", 1)])
    await blocks_collection.create_index("user_id", unique=True)
    await blocks_collection.create_index("blocked")

    # Moderation logs (align with fields you actually write)
    await moderation_logs.create_index([("admin_id", 1), ("created_at", -1)])
    await moderation_logs.create_index([("report_id", 1)])

    # ==============================
    # Friend graph (NEW indexes)
    # ==============================

    # Friend Profiles — prevent duplicates per owner and speed lookups
    # NOTE: your documents include `friend_id` (created via FriendCreate), so this is valid.
    await friend_collection.create_index(
        [("user_id", 1), ("friend_id", 1)],
        unique=True,
        name="user_friend_unique",
    )
    # Helpful for listing your friends fast (GET /friend)
    await friend_collection.create_index(
        [("user_id", 1), ("created_at", -1)],
        name="user_createdAt_desc",
    )

    # Friend Requests — fast pair/status checks & inbox/outbox lists
    await friend_requests_collection.create_index(
        [("from_user_id", 1), ("to_user_id", 1), ("status", 1)],
        name="request_pair_status",
    )
    await friend_requests_collection.create_index(
        [("to_user_id", 1), ("status", 1), ("created_at", -1)],
        name="to_status_createdAt_desc",
    )
    await friend_requests_collection.create_index(
        [("from_user_id", 1), ("status", 1), ("created_at", -1)],
        name="from_status_createdAt_desc",
    )

    # If later you choose DB-enforced "only one pending per pair", add:
    # await friend_requests_collection.create_index(
    #     [("pair_key", 1)],
    #     unique=True,
    #     partialFilterExpression={"status": "pending"},
    #     name="unique_pending_per_pair",
    # )
