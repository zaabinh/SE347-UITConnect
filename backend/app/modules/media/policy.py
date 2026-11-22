"""Media limits and read authorization approved in issue #5."""

from dataclasses import dataclass
from uuid import UUID

MAX_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 8_000_000
UPLOAD_TTL = 300
RESTRICTED_READ_TTL = 60
ACTIVE_READ_TTL = 300


class MediaError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def upload_key(owner_id: str, media_id: str) -> str:
    return f"pending/{UUID(owner_id)}/{UUID(media_id)}"


def final_key(owner_id: str, media_id: str, attempt_id: str, content_type: str) -> str:
    extension = {"image/jpeg": "jpg", "image/png": "png"}.get(content_type)
    if extension is None:
        raise MediaError("MEDIA_TYPE_NOT_ALLOWED")
    return f"post-covers/{UUID(owner_id)}/{UUID(media_id)}/{UUID(attempt_id)}.{extension}"


@dataclass(frozen=True)
class ReadContext:
    """Populate only from database records, never from client assertions."""

    viewer_id: str
    media_owner_id: str
    media_status: str
    viewer_active: bool
    profile_completed: bool
    viewer_is_admin: bool = False
    post_status: str | None = None
    is_share: bool = False
    original_post_status: str | None = None
    share_owner_id: str | None = None


def read_ttl(context: ReadContext) -> int:
    if not context.viewer_active or not context.profile_completed:
        raise MediaError("FORBIDDEN")
    if context.media_status != "ready":
        raise MediaError("MEDIA_NOT_READY")
    privileged = context.viewer_is_admin or context.viewer_id == context.media_owner_id
    allowed_statuses = {"active", "pending", "rejected"}
    if context.is_share:
        # A removed/missing original suppresses the share image, including for admins.
        if context.original_post_status not in allowed_statuses:
            raise MediaError("NOT_FOUND")
        if context.original_post_status != "active" and not privileged:
            raise MediaError("NOT_FOUND")
        if context.post_status not in allowed_statuses:
            raise MediaError("NOT_FOUND")
        if context.post_status != "active" and not (
            context.viewer_is_admin or context.viewer_id == context.share_owner_id
        ):
            raise MediaError("NOT_FOUND")
        return (ACTIVE_READ_TTL if context.post_status == context.original_post_status == "active"
                else RESTRICTED_READ_TTL)
    if context.post_status == "active":
        return ACTIVE_READ_TTL
    if context.post_status in {None, "pending", "rejected"} and privileged:
        return RESTRICTED_READ_TTL
    raise MediaError("NOT_FOUND")
