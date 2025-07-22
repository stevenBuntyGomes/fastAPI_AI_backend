from datetime import datetime
from dotenv import load_dotenv
import os
from pymongo import MongoClient

# Load .env
load_dotenv()
MONGO_URL = os.getenv("MONGODB_URL")

# Connect to DB
client = MongoClient(MONGO_URL)
db = client.voice_ai
milestone_collection = db["milestone"]

# Static milestones
MILESTONES = [
    {"time_in_minutes": 20, "name": "Heart Reset", "description": "Your heart rate and blood pressure start dropping towards normal levels."},
    {"time_in_minutes": 120, "name": "Craving Spike", "description": "First cravings hit, but every hour without vaping builds your control."},
    {"time_in_minutes": 600, "name": "Blood Flow Boost", "description": "Circulation improves, oxygen starts flowing better throughout your body."},
    {"time_in_minutes": 1440, "name": "Breakthrough Mark", "description": "Nicotine starts leaving your system, cravings peak but you’re stronger."},
    {"time_in_minutes": 4320, "name": "Body Reboot", "description": "Breathing, taste, and smell begin noticeably improving, first real health shift."},
    {"time_in_minutes": 10080, "name": "Cravings Crash", "description": "Major cravings fade significantly, you’re through the hardest mental barrier."},
    {"time_in_minutes": 20160, "name": "Clear Head Zone", "description": "Mood, focus, and mental sharpness noticeably bounce back."},
    {"time_in_minutes": 43200, "name": "Energy Return", "description": "Energy levels improve, breathing feels easier, stamina starts coming back."},
    {"time_in_minutes": 86400, "name": "Willpower Badge", "description": "You’ve resisted cravings for two months; discipline is locked in."},
    {"time_in_minutes": 129600, "name": "Nicotine-Free Badge", "description": "Body is nicotine-free, lung repair and deeper healing are well underway."},
    {"time_in_minutes": 172800, "name": "Lung Vitality Rise", "description": "Lung function noticeably improves, your breathing feels smoother and stronger."},
    {"time_in_minutes": 216000, "name": "Respiratory Renewal", "description": "Breathing is easier, lungs feel stronger with reduced inflammation."},
    {"time_in_minutes": 259200, "name": "Lung Repair Phase", "description": "Lung function improves dramatically; you’re reversing real damage now."},
    {"time_in_minutes": 388800, "name": "Airway Strength Badge", "description": "Airways are stronger, overall lung health approaches a non-vaper’s baseline."},
    {"time_in_minutes": 525600, "name": "GOAT", "description": "Your heart and lung health show major recovery, relapse risk drops significantly."}
]

# OPTIONAL: clear collection before inserting (only for dev)
milestone_collection.delete_many({})

# Insert milestones
for milestone in MILESTONES:
    milestone["created_at"] = datetime.utcnow()
    milestone_collection.insert_one(milestone)

print("✅ Static milestones inserted successfully.")
