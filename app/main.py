from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.chat import router as chat_router
from app.routes.auth import router as auth_router
from app.routes.progress import router as progress_router
from app.routes.lung_check import router as lung_check_router
from app.routes.lung_relining import router as lung_relining_router
from app.routes.recovery import router as recovery_router

app = FastAPI(title="Voice AI Backend", version="1.0.0")

# ✅ CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",                     # Local dev
        "https://fast-api-frontend-ts.vercel.app",   # Vercel production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Health check route
@app.get("/health")
def health_check():
    return {"status": "✅ OK", "message": "FastAPI backend is running."}

# ✅ Optional root route
@app.get("/")
def root():
    return {"message": "👋 Welcome to the Voice AI Backend!"}

# ✅ Include API routers
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(progress_router)
app.include_router(lung_check_router)
app.include_router(lung_relining_router)
app.include_router(recovery_router)
