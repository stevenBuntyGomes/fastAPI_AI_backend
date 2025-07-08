from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL")

client = AsyncIOMotorClient(MONGO_URL)
db = client.voice_ai  # your main database

memory_collection = db.user_memory     # for AI chat memory
users_collection = db.users            # for auth-related users
