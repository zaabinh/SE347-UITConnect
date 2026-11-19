from fastapi import APIRouter, File, Request, UploadFile
from app.modules.posts import upload_application


router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/image")
async def upload_image(request: Request, file: UploadFile = File(...)):
    return upload_application.upload_image(file, str(request.base_url))
