"""Bounded image validation and filesystem storage, independent of HTTP."""

import os
import uuid

from app.core.config import settings
from app.core.exceptions import ApplicationError


UPLOAD_DIR = settings.upload_dir
PUBLIC_API_URL = str(settings.public_api_url).rstrip('/') if settings.public_api_url else ''
MAX_IMAGE_BYTES = 5 * 1024 * 1024
CHUNK_BYTES = 64 * 1024


def upload_image(file, request_base_url):
    extensions = {'image/jpeg': 'jpg', 'image/png': 'png'}
    extension = extensions.get(file.content_type)
    if extension is None:
        raise ApplicationError(400, 'Invalid file type. Only JPEG and PNG are accepted.')

    path = None
    created = False
    try:
        first = file.file.read(CHUNK_BYTES)
        signature_matches = (first.startswith(b'\xff\xd8\xff') if extension == 'jpg'
                             else first.startswith(b'\x89PNG\r\n\x1a\n'))
        if not signature_matches:
            raise ApplicationError(400, 'Image content does not match its declared type.')

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filename = f'{uuid.uuid4()}.{extension}'
        path = os.path.join(UPLOAD_DIR, filename)
        total = 0
        with open(path, 'xb') as destination:
            created = True
            chunk = first
            while chunk:
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise ApplicationError(413, 'Image exceeds the 5 MiB limit.')
                destination.write(chunk)
                chunk = file.file.read(min(CHUNK_BYTES, MAX_IMAGE_BYTES - total + 1))
    except Exception as exc:
        if created:
            try:
                os.remove(path)
            except OSError:
                pass
        if isinstance(exc, ApplicationError):
            raise
        raise ApplicationError(500, 'Unable to save image.') from exc

    base_url = PUBLIC_API_URL or str(request_base_url).rstrip('/')
    return {'url': f'{base_url}/uploads/{filename}'}
