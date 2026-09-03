import os
import uuid

import cloudinary
import cloudinary.uploader
from cloudinary import CloudinaryImage


# ============================================================
# CLOUDINARY CONFIGURATION
# ============================================================

CLOUDINARY_CLOUD_NAME = os.getenv(
    "CLOUDINARY_CLOUD_NAME",
    ""
).strip()

CLOUDINARY_API_KEY = os.getenv(
    "CLOUDINARY_API_KEY",
    ""
).strip()

CLOUDINARY_API_SECRET = os.getenv(
    "CLOUDINARY_API_SECRET",
    ""
).strip()


cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)


# ============================================================
# SETTINGS
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp"
}


def cloudinary_is_configured():
    return all([
        CLOUDINARY_CLOUD_NAME,
        CLOUDINARY_API_KEY,
        CLOUDINARY_API_SECRET
    ])


def configuration_error():
    missing = []

    if not CLOUDINARY_CLOUD_NAME:
        missing.append("CLOUDINARY_CLOUD_NAME")

    if not CLOUDINARY_API_KEY:
        missing.append("CLOUDINARY_API_KEY")

    if not CLOUDINARY_API_SECRET:
        missing.append("CLOUDINARY_API_SECRET")

    return (
        "Cloudinary is not configured. "
        "Missing environment variable(s): "
        + ", ".join(missing)
    )


# ============================================================
# IMAGE VALIDATION
# ============================================================

def is_allowed_image(filename):
    if not filename:
        return False

    filename = filename.lower().strip()

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1]

    return extension in ALLOWED_IMAGE_EXTENSIONS


# ============================================================
# UPLOAD IMAGE
# ============================================================

def upload_image(file_storage, key_prefix="uploads"):

    if not file_storage:
        return None

    if not file_storage.filename:
        return None

    if not is_allowed_image(file_storage.filename):
        return None

    if not cloudinary_is_configured():
        raise RuntimeError(configuration_error())

    folder = str(
        key_prefix or "uploads"
    ).strip("/")

    public_id = uuid.uuid4().hex

    result = cloudinary.uploader.upload(
        file_storage.stream,
        folder=folder,
        public_id=public_id,
        resource_type="image",
        overwrite=False,
        unique_filename=False,
        use_filename=False
    )

    return result.get("public_id")


# ============================================================
# GENERATE PUBLIC URL
# ============================================================

def public_url(key):

    if not key:
        return None

    if not cloudinary_is_configured():
        raise RuntimeError(configuration_error())

    return CloudinaryImage(key).build_url(
        secure=True
    )
