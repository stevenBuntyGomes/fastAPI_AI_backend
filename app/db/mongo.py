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
friend_collection = db["friends"]
mypod_collection = db["mypods"]

# OPTIONAL but recommended: call this once at startup to ensure indexes exist.
async def init_db_indexes() -> None:
    # Users: unique email
    await users_collection.create_index("email", unique=True)
    # Map user -> sockets quickly
    await socket_sessions_collection.create_index([("user_id", 1)])
    await socket_sessions_collection.create_index([("sid", 1)], unique=True)

    await devices_collection.create_index([("user_id", 1), ("platform", 1)], unique=True)
    await devices_collection.create_index("updated_at")

    await bumps_collection.create_index([("to_user_id", 1), ("created_at", -1)])
    await bumps_collection.create_index([("from_user_id", 1), ("created_at", -1)])

    # Verification codes: one code per email, auto-expire at 'expires'
    await verification_codes_collection.create_index("email", unique=True)
    # TTL index: documents expire at the exact datetime in 'expires'
    await verification_codes_collection.create_index("expires", expireAfterSeconds=0)

    # Onboarding: handy for recent lookups
    await onboarding_collection.create_index("created_at")
