"""Bounded snapshot verification, to run in an isolated worker before HTTP integration."""

from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from .policy import MAX_BYTES, MAX_DIMENSION, MAX_PIXELS, MediaError


@dataclass(frozen=True)
class VerifiedImage:
    data: bytes = field(repr=False)
    content_type: str
    extension: str
    width: int
    height: int
    sha256: str


def verify_image(data: bytes, *, filename: str, content_type: str, declared_size: int) -> VerifiedImage:
    if not data or len(data) > MAX_BYTES or not 1 <= declared_size <= MAX_BYTES:
        raise MediaError("PAYLOAD_TOO_LARGE")
    if len(data) != declared_size:
        raise MediaError("MEDIA_METADATA_MISMATCH")
    suffix = filename.rsplit(".", 1)[-1].lower()
    valid_suffixes = {"image/jpeg": {"jpg", "jpeg"}, "image/png": {"png"}}
    if (content_type not in valid_suffixes or suffix not in valid_suffixes[content_type]
            or not 1 <= len(filename) <= 255 or filename.count(".") != 1
            or any(c in filename for c in ("/", "\\")) or any(ord(c) < 32 for c in filename)):
        raise MediaError("MEDIA_TYPE_NOT_ALLOWED")
    expected_format = "JPEG" if content_type == "image/jpeg" else "PNG"
    try:
        with Image.open(BytesIO(data), formats=["JPEG", "PNG"]) as source:
            if source.format != expected_format:
                raise MediaError("MEDIA_METADATA_MISMATCH")
            width, height = source.size
            if (width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS
                    or getattr(source, "n_frames", 1) != 1):
                raise MediaError("MEDIA_INVALID_IMAGE")
            source.load()
            oriented = ImageOps.exif_transpose(source)
            converted = oriented.convert("RGB" if expected_format == "JPEG" else "RGBA")
            try:
                converted.info.clear()
                output = BytesIO()
                converted.save(output, format=expected_format)
                result = output.getvalue()
                if len(result) > MAX_BYTES:
                    raise MediaError("PAYLOAD_TOO_LARGE")
                return VerifiedImage(result, content_type, "jpg" if expected_format == "JPEG" else "png",
                                     converted.width, converted.height, sha256(result).hexdigest())
            finally:
                converted.close()
                oriented.close()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise MediaError("MEDIA_INVALID_IMAGE") from None
