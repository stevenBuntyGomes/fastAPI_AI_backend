from fastapi import APIRouter
from ..schemas.auth_schema import Base64ImageUploadRequest, ImageUploadResponse
from ..services.cloudinary_service import upload_base64_image

upload_router = APIRouter(prefix="/upload", tags=["Upload"])

@upload_router.post("/image", response_model=ImageUploadResponse, summary="Upload base64 image to Cloudinary and get URL")
async def upload_image(payload: Base64ImageUploadRequest):
    url, public_id = upload_base64_image(payload.image_base64, payload.folder)
    return ImageUploadResponse(url=url, public_id=public_id)
