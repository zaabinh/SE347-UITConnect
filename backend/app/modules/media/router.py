from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.modules.auth.dependencies import require_active_verified_user
from app.modules.media import application
from app.modules.media.schemas import UploadImageResponse
from app.modules.users.models import User


router = APIRouter(prefix='/media', tags=['Media'])


@router.post('/images', response_model=UploadImageResponse,
             status_code=status.HTTP_201_CREATED, operation_id='media_upload_image')
def upload_image(request: Request, file: UploadFile = File(...),
                 current_user: User = Depends(require_active_verified_user)):
    return application.upload_image(file, str(request.base_url))
