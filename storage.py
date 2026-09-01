import io
import os
import uuid

import boto3
from botocore.client import Config


# ============================================================
# CLOUDFLARE R2 CONFIGURATION
# ============================================================
#
# Required environment variables:
#   R2_ACCOUNT_ID         - Cloudflare account ID
#   R2_ACCESS_KEY_ID      - R2 API token access key
#   R2_SECRET_ACCESS_KEY  - R2 API token secret key
#   R2_BUCKET_NAME         - Name of the R2 bucket
#   R2_PUBLIC_URL           - Public dev/custom domain URL for the bucket,
#                             e.g. https://pub-xxxx.r2.dev. All images in
#                             this app (complaint photos, admin replies,
#                             updates) are shown to whoever holds the
#                             tracking link or visits the public updates
#                             page, so the bucket should have public
#                             access enabled.

_R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
_R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
_R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def is_allowed_image(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def upload_image(file_storage, key_prefix):
    """
    Upload a Werkzeug FileStorage image to R2 and return its object key.
    Returns None if the file isn't a recognized image type.
    """

    if not file_storage or not file_storage.filename:
        return None

    if not is_allowed_image(file_storage.filename):
        return None

    extension = file_storage.filename.rsplit(".", 1)[1].lower()
    key = f"{key_prefix}/{uuid.uuid4().hex}.{extension}"

    _client().upload_fileobj(
        file_storage.stream,
        _R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": file_storage.mimetype or "image/jpeg"},
    )

    return key


def public_url(key):
    """Build the public URL for an object key. Returns None if key is falsy."""

    if not key:
        return None

    if not _R2_PUBLIC_URL:
        raise RuntimeError("R2_PUBLIC_URL is not configured.")

    return f"{_R2_PUBLIC_URL}/{key}"
