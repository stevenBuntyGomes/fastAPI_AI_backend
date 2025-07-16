from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get MongoDB connection URL
MONGO_URL = os.getenv("MONGODB_URL")

# Initialize MongoDB client
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