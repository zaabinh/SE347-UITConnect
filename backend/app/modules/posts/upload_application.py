"""Image upload validation and filesystem work, independent of HTTP."""

import os
import shutil
import uuid
from app.core.config import settings
from app.core.exceptions import ApplicationError


UPLOAD_DIR = settings.upload_dir
PUBLIC_API_URL = str(settings.public_api_url).rstrip("/") if settings.public_api_url else ""


def upload_image(file, request_base_url):
    if file.content_type not in {"image/jpeg", "image/png", "image/jpg"}:
        raise ApplicationError(status_code=400, detail="Invalid file type. Only JPG and PNG are accepted.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_extension = (file.filename or "").rsplit(".", 1)[-1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise ApplicationError(status_code=500, detail=f"Unable to save file: {exc}") from exc

    base_url = PUBLIC_API_URL or str(request_base_url).rstrip("/")
    return {"url": f"{base_url}/uploads/{unique_filename}"}
