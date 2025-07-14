# app/routes/lung_relining.py

from fastapi import APIRouter, Depends
from typing import List
from app.schemas.lung_relining_schema import (
    LungReliningCreateRequest,
    LungReliningResponse,
)
from app.controllers import lung_relining_controller
from ..utils.auth_utils import get_current_user

router = APIRouter()

@router.post("/lung-relining", response_model=LungReliningResponse)
async def create_lung_relining_entry(
    data: LungReliningCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    return await lung_relining_controller.create_lung_relining_entry(data, current_user)

@router.get("/lung-relining/me", response_model=List[LungReliningResponse])
async def get_user_lung_relining_entries(
    current_user: dict = Depends(get_current_user)
):
    return await lung_relining_controller.get_user_lung_relining_entries(current_user)
