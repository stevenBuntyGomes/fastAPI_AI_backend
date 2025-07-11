# app/database/mongo.py
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL")

client = AsyncIOMotorClient(MONGO_URL)
db = client.voice_ai

users_collection = db.users
verification_codes_collection = db.codes
memory_collection = db.user_memory
