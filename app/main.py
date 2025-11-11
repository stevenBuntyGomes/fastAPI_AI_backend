# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.mongo import init_db_indexes

# Routers
from app.routes.chat import router as chat_router
from app.routes.auth import router as auth_router
from app.routes.progress import router as progress_router
from app.routes.lung_check import router as lung_check_router
from app.routes.lung_relining import router as lung_relining_router
from app.routes.recovery import router as recovery_router
from app.routes.community import router as community_router
from app.routes.friend import router as friend_router
from app.routes.mypod_routes import router as mypod_router
from app.routes.milestone import router as milestone_router
from app.routes.onboarding import router as onboarding_router
from app.routes.devices import router as devices_router
from app.routes.bump import router as bump_router  # APNs-only bump
from app.routes.referral import router as referral_router
from app.routes.legal import router as legal_router
from app.routes.safety import router as safety_router
from app.routes.moderation_admin import router as moderation_admin_router
from app.routes.social_achievement_routes import router as social_achievement_router
from app.routes.upload import upload_router

# ---------------------------
# Build FastAPI app
# ---------------------------
fastapi_app = FastAPI(title="Voice AI Backend", version="1.0.0")

# CORS — keep wide open for now; tighten for production if needed
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@fastapi_app.get("/health")
async def health_check():
    return {"status": "✅ OK", "message": "FastAPI backend is running."}

@fastapi_app.get("/")
async def root():
    return {"message": "👋 Welcome to the Voice AI Backend!"}

# ---------------------------
# Routers
# ---------------------------
fastapi_app.include_router(chat_router)
fastapi_app.include_router(auth_router)
fastapi_app.include_router(onboarding_router)
fastapi_app.include_router(progress_router)
fastapi_app.include_router(lung_check_router)
fastapi_app.include_router(lung_relining_router)
fastapi_app.include_router(recovery_router)
fastapi_app.include_router(community_router)
fastapi_app.include_router(friend_router)
fastapi_app.include_router(mypod_router)
fastapi_app.include_router(milestone_router)
fastapi_app.include_router(referral_router)
fastapi_app.include_router(social_achievement_router)

# APNs device registration + bump push (no Socket.IO)
fastapi_app.include_router(devices_router)
fastapi_app.include_router(bump_router)
fastapi_app.include_router(legal_router)
fastapi_app.include_router(safety_router)
fastapi_app.include_router(moderation_admin_router)
fastapi_app.include_router(upload_router)



# ---------------------------
# Startup tasks
# ---------------------------
@fastapi_app.on_event("startup")
async def on_startup():
    try:
        await init_db_indexes()
    except Exception as e:
        # Don't crash the app if indexes fail; just log it
        print("Index init error:", e)

# ---------------------------
# Final ASGI app export (no Socket.IO wrapper)
# ---------------------------
app = fastapi_app
