import os
from fastapi import HTTPException, status
import cloudinary
from cloudinary.uploader import upload as cld_upload

# Configure once
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

def _coerce_data_url(image_base64: str) -> str:
    """
    Accepts raw base64 or data URL. If no data URL header, assume PNG.
    """
    if not image_base64 or not str(image_base64).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_base64 is required")
    b64 = image_base64.strip()
    if b64.startswith("data:") and ";base64," in b64:
        return b64
    # raw base64 → wrap as data URL (png default)
    return f"data:image/png;base64,{b64}"

def upload_base64_image(image_base64: str, folder: str | None = None) -> tuple[str, str | None]:
    """
    Uploads base64 image to Cloudinary. Returns (secure_url, public_id).
    """
    try:
        file_data = _coerce_data_url(image_base64)
        folder_final = folder or os.getenv("CLOUDINARY_UPLOAD_FOLDER", "user_uploads")
        res = cld_upload(file_data, folder=folder_final, overwrite=True, resource_type="image")
        url = res.get("secure_url")
        public_id = res.get("public_id")
        if not url:
            raise RuntimeError("Cloudinary did not return secure_url")
        return url, public_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Upload failed: {e}")
