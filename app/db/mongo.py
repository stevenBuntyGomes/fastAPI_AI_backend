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

    # Verification codes: one code per email, auto-expire at 'expires'
    await verification_codes_collection.create_index("email", unique=True)
    # TTL index: documents expire at the exact datetime in 'expires'
    await verification_codes_collection.create_index("expires", expireAfterSeconds=0)

    # Onboarding: handy for recent lookups
    await onboarding_collection.create_index("created_at")
