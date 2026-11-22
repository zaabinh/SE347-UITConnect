from dataclasses import replace
from io import BytesIO
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import boto3
import pytest
from botocore.config import Config
from botocore.response import StreamingBody
from botocore.stub import Stubber
from PIL import Image, PngImagePlugin

from app.modules.media.policy import MAX_BYTES, MediaError, ReadContext, read_ttl, upload_key, final_key
from app.modules.media.storage import R2Config, R2Storage
from app.modules.media.verification import verify_image

OWNER = "11111111-1111-4111-8111-111111111111"
MEDIA = "22222222-2222-4222-8222-222222222222"
ATTEMPT = "33333333-3333-4333-8333-333333333333"
UPLOAD = upload_key(OWNER, MEDIA)
FINAL = final_key(OWNER, MEDIA, ATTEMPT, "image/png")


def image_bytes(size=(40, 30), fmt="PNG"):
    output = BytesIO()
    with Image.new("RGB", size, (30, 80, 120)) as image:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private", "must disappear")
        image.save(output, format=fmt, **({"pnginfo": metadata} if fmt == "PNG" else {}))
    return output.getvalue()


@pytest.fixture
def storage():
    config = R2Config("https://" + "a" * 32 + ".r2.cloudflarestorage.com",
                      "test-uploads", "test-media", "test-access", "test-secret")
    client = boto3.client("s3", endpoint_url=config.endpoint_url, region_name="auto",
                          aws_access_key_id=config.access_key_id,
                          aws_secret_access_key=config.secret_access_key,
                          config=Config(signature_version="s3v4"))
    return R2Storage(config, client=client)


def test_presigned_scope_headers_and_ttl_without_network(storage):
    with Stubber(storage.client):
        url = storage.create_upload_url(UPLOAD, "image/png")
        query = parse_qs(urlsplit(url).query)
        assert query["X-Amz-Expires"] == ["300"]
        assert "content-type" in query["X-Amz-SignedHeaders"][0]
        assert "test-uploads" in url and UPLOAD in url
        for ttl in (60, 300):
            read = storage.create_read_url(FINAL, ttl)
            assert parse_qs(urlsplit(read).query)["X-Amz-Expires"] == [str(ttl)]
            assert "test-media" in read
    assert "test-secret" not in repr(storage.config)


def test_bounded_read_closes_stream_and_catches_head_get_race(storage):
    stream = BytesIO(b"x" * (MAX_BYTES + 20))
    body = StreamingBody(stream, MAX_BYTES + 20)
    with Stubber(storage.client) as stub:
        params = {"Bucket": "test-uploads", "Key": UPLOAD}
        stub.add_response("head_object", {"ContentLength": 1}, params)
        stub.add_response("get_object", {"Body": body}, params)
        with pytest.raises(MediaError, match="PAYLOAD_TOO_LARGE"):
            storage.read_upload(UPLOAD)
    assert stream.closed


def test_missing_and_storage_errors_are_safe_and_delete_is_repeatable(storage):
    params = {"Bucket": "test-uploads", "Key": UPLOAD}
    with Stubber(storage.client) as stub:
        stub.add_client_error("head_object", "NoSuchKey", "private provider details", 404, expected_params=params)
        with pytest.raises(MediaError, match="^MEDIA_NOT_UPLOADED$"):
            storage.read_upload(UPLOAD)
        stub.add_client_error("head_object", "AccessDenied", "credentials and URL", 403, expected_params=params)
        with pytest.raises(MediaError, match="^MEDIA_STORAGE_UNAVAILABLE$"):
            storage.read_upload(UPLOAD)
        stub.add_response("delete_object", {}, params)
        stub.add_client_error("delete_object", "NoSuchKey", http_status_code=404, expected_params=params)
        storage.delete(UPLOAD)
        storage.delete(UPLOAD)


def test_successful_read_and_write_use_different_buckets(storage):
    data = image_bytes()
    verified = verify_image(data, filename="cover.png", content_type="image/png", declared_size=len(data))
    stream = BytesIO(data)
    with Stubber(storage.client) as stub:
        params = {"Bucket": "test-uploads", "Key": UPLOAD}
        stub.add_response("head_object", {"ContentLength": len(data)}, params)
        stub.add_response("get_object", {"Body": StreamingBody(stream, len(data))}, params)
        assert storage.read_upload(UPLOAD) == data
        stub.add_response("put_object", {}, {"Bucket": "test-media", "Key": FINAL,
            "Body": verified.data, "ContentType": "image/png", "CacheControl": "private, no-store",
            "ContentDisposition": 'inline; filename="image.png"'})
        storage.write_verified(FINAL, verified)
    assert stream.closed


@pytest.mark.parametrize("key", ["pending/../secret", "post-covers/a", "pending/a\\b", "pending//a"])
def test_invalid_upload_keys_never_call_sdk(storage, key):
    storage.client = Mock()
    with pytest.raises(MediaError):
        storage.create_upload_url(key, "image/png")
    assert not storage.client.mock_calls


@pytest.mark.parametrize("fmt,mime,filename", [("PNG", "image/png", "cover.png"), ("JPEG", "image/jpeg", "cover.jpg")])
def test_verify_reencodes_and_removes_metadata(fmt, mime, filename):
    data = image_bytes(fmt=fmt)
    result = verify_image(data, filename=filename, content_type=mime, declared_size=len(data))
    assert (result.width, result.height) == (40, 30)
    with Image.open(BytesIO(result.data)) as image:
        assert "private" not in image.info
        assert not image.getexif()
        image.load()


@pytest.mark.parametrize("size", [(4097, 1), (4000, 2001)])
def test_review_dimension_and_eight_million_pixel_limit(size):
    data = image_bytes(size)
    with pytest.raises(MediaError, match="MEDIA_INVALID_IMAGE"):
        verify_image(data, filename="cover.png", content_type="image/png", declared_size=len(data))


@pytest.mark.parametrize("data,mime,name,declared,code", [
    (b"not an image", "image/png", "x.png", 12, "MEDIA_INVALID_IMAGE"),
    (b"abc", "image/png", "x.png", 4, "MEDIA_METADATA_MISMATCH"),
    (b"abc", "image/png", "x.exe.png", 3, "MEDIA_TYPE_NOT_ALLOWED"),
    (b"abc", "image/png", "../x.png", 3, "MEDIA_TYPE_NOT_ALLOWED"),
    (b"abc", "image/svg+xml", "x.svg", 3, "MEDIA_TYPE_NOT_ALLOWED"),
])
def test_bad_files(data, mime, name, declared, code):
    with pytest.raises(MediaError, match=code):
        verify_image(data, filename=name, content_type=mime, declared_size=declared)


def test_header_mismatch_and_animation():
    data = image_bytes()
    with pytest.raises(MediaError, match="MEDIA_METADATA_MISMATCH"):
        verify_image(data, filename="x.jpg", content_type="image/jpeg", declared_size=len(data))
    output = BytesIO()
    with Image.new("RGB", (20, 20), "red") as first, Image.new("RGB", (20, 20), "blue") as second:
        first.save(output, format="PNG", save_all=True, append_images=[second], duration=100)
    data = output.getvalue()
    with pytest.raises(MediaError, match="MEDIA_INVALID_IMAGE"):
        verify_image(data, filename="x.png", content_type="image/png", declared_size=len(data))


def context(**overrides):
    return replace(ReadContext(OWNER, OWNER, "ready", True, True), **overrides)


@pytest.mark.parametrize("post_status,ttl", [(None, 60), ("pending", 60), ("rejected", 60), ("active", 300)])
def test_read_ttl_depends_on_visibility(post_status, ttl):
    assert read_ttl(context(post_status=post_status)) == ttl


@pytest.mark.parametrize("changes", [
    {"viewer_active": False}, {"profile_completed": False}, {"media_status": "pending"},
    {"post_status": "deleted"}, {"viewer_id": "other", "post_status": "pending"},
    {"is_share": True, "post_status": "active", "original_post_status": "deleted"},
    {"is_share": True, "post_status": "active", "original_post_status": None},
    {"is_share": True, "viewer_id": "other", "share_owner_id": "other",
     "post_status": "active", "original_post_status": "rejected"},
])
def test_read_denials_including_share_original_hidden(changes):
    with pytest.raises(MediaError):
        read_ttl(context(**changes))


def test_share_requires_both_contexts_and_uses_shorter_ttl():
    assert read_ttl(context(is_share=True, post_status="active", original_post_status="active")) == 300
    assert read_ttl(context(is_share=True, post_status="active", original_post_status="rejected")) == 60
    assert read_ttl(context(is_share=True, post_status="pending", original_post_status="active",
                            share_owner_id=OWNER)) == 60
