"""Private R2 operations; no database work or network access at import time."""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from .policy import MAX_BYTES, UPLOAD_TTL, MediaError


@dataclass(frozen=True)
class R2Config:
    endpoint_url: str
    uploads_bucket: str
    media_bucket: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)

    def __post_init__(self):
        url = urlsplit(self.endpoint_url)
        if (url.scheme != "https" or not re.fullmatch(
            r"[a-f0-9]{32}(?:\.(?:eu|fedramp))?\.r2\.cloudflarestorage\.com", url.hostname or ""
        ) or url.username or url.password or url.port or url.path not in {"", "/"}
                or url.query or url.fragment):
            raise ValueError("Use the account's HTTPS R2 S3 endpoint")
        for bucket in (self.uploads_bucket, self.media_bucket):
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
                raise ValueError("Invalid R2 bucket name")
        if self.uploads_bucket == self.media_bucket:
            raise ValueError("Upload and verified media buckets must differ")
        if not self.access_key_id.strip() or not self.secret_access_key.strip():
            raise ValueError("Explicit R2 credentials are required")


class R2Storage:
    def __init__(self, config: R2Config, *, client=None):
        self.config = config
        self.client = client if client is not None else boto3.client(
            "s3", endpoint_url=config.endpoint_url, region_name="auto",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=15,
                          retries={"max_attempts": 2, "mode": "standard"}),
        )

    @staticmethod
    def _key(key: str, prefix: str):
        # Caller supplies keys loaded from owned metadata, never user filenames.
        if not key.startswith(prefix) or any(p in {"", ".", ".."} for p in key.split("/")):
            raise MediaError("MEDIA_INVALID_KEY")
        if "\\" in key or any(ord(c) < 32 for c in key) or len(key) > 512:
            raise MediaError("MEDIA_INVALID_KEY")

    def _call(self, operation, **kwargs):
        try:
            return getattr(self.client, operation)(**kwargs)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise MediaError("MEDIA_NOT_UPLOADED") from None
            raise MediaError("MEDIA_STORAGE_UNAVAILABLE") from None
        except BotoCoreError:
            raise MediaError("MEDIA_STORAGE_UNAVAILABLE") from None

    def create_upload_url(self, key: str, content_type: str) -> str:
        self._key(key, "pending/")
        if content_type not in {"image/jpeg", "image/png"}:
            raise MediaError("MEDIA_TYPE_NOT_ALLOWED")
        return self._call("generate_presigned_url", ClientMethod="put_object", Params={
            "Bucket": self.config.uploads_bucket, "Key": key, "ContentType": content_type,
        }, ExpiresIn=UPLOAD_TTL, HttpMethod="PUT")

    def read_upload(self, key: str) -> bytes:
        self._key(key, "pending/")
        info = self._call("head_object", Bucket=self.config.uploads_bucket, Key=key)
        if info["ContentLength"] > MAX_BYTES:
            raise MediaError("PAYLOAD_TOO_LARGE")
        response = self._call("get_object", Bucket=self.config.uploads_bucket, Key=key)
        body = response["Body"]
        try:
            data = bytearray()
            while len(data) <= MAX_BYTES:
                chunk = body.read(min(65536, MAX_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise MediaError("PAYLOAD_TOO_LARGE")
            return bytes(data)
        except (BotoCoreError, OSError):
            raise MediaError("MEDIA_STORAGE_UNAVAILABLE") from None
        finally:
            body.close()

    def write_verified(self, key: str, image) -> None:
        self._key(key, "post-covers/")
        self._call("put_object", Bucket=self.config.media_bucket, Key=key, Body=image.data,
                   ContentType=image.content_type, CacheControl="private, no-store",
                   ContentDisposition='inline; filename="image.' + image.extension + '"')

    def create_read_url(self, key: str, ttl: int) -> str:
        self._key(key, "post-covers/")
        if ttl not in {60, 300}:
            raise ValueError("Read TTL must come from the visibility policy")
        return self._call("generate_presigned_url", ClientMethod="get_object", Params={
            "Bucket": self.config.media_bucket, "Key": key,
        }, ExpiresIn=ttl, HttpMethod="GET")

    def delete(self, key: str, *, verified: bool = False) -> None:
        self._key(key, "post-covers/" if verified else "pending/")
        try:
            self._call("delete_object", Bucket=(self.config.media_bucket if verified
                       else self.config.uploads_bucket), Key=key)
        except MediaError as exc:
            if exc.code != "MEDIA_NOT_UPLOADED":
                raise
