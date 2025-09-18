# app/routes/milestone.py
from fastapi import APIRouter
from typing import List, Dict

from ..controllers.milestone_controller import seed_milestones, list_milestones

router = APIRouter(prefix="/milestone", tags=["Milestone"])

# 🔓 Seed via browser or curl (no auth) — remove or protect in prod.
@router.get("/seed", summary="Seed milestones (no auth)")
async def seed_milestones_get():
    return await seed_milestones()

# Same seed but POST, if you prefer
@router.post("/seed", summary="Seed milestones (no auth)")
async def seed_milestones_post():
    return await seed_milestones()

@router.get("/", summary="List milestones (sorted by minutes)")
async def get_milestones():
    return await list_milestones()
