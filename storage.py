import os
import uuid

import cloudinary
import cloudinary.uploader


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


# ============================================================
# CONFIGURE CLOUDINARY
# ============================================================

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)


# ============================================================
# CLOUDINARY STATUS
# ============================================================

def cloudinary_is_configured():
    """
    Check whether Cloudinary has been configured.
    """

    return all([
        CLOUDINARY_CLOUD_NAME,
        CLOUDINARY_API_KEY,
        CLOUDINARY_API_SECRET,
    ])


def _configuration_error():
    """
    Return a useful configuration error.
    """

    missing = []

    if not CLOUDINARY_CLOUD_NAME:
        missing.append(
            "CLOUDINARY_CLOUD_NAME"
        )

    if not CLOUDINARY_API_KEY:
        missing.append(
            "CLOUDINARY_API_KEY"
        )

    if not CLOUDINARY_API_SECRET:
        missing.append(
            "CLOUDINARY_API_SECRET"
        )

    return (
        "Cloudinary is not configured correctly. "
        "Missing environment variables: "
        + ", ".join(missing)
    )


# ============================================================
# IMAGE VALIDATION
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
}


def is_allowed_image(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = (
        filename
        .rsplit(".", 1)[1]
        .lower()
    )

    return extension in ALLOWED_IMAGE_EXTENSIONS


# ============================================================
# UPLOAD IMAGE
# ============================================================

def upload_image(
    file_storage,
    key_prefix
):
    """
    Upload a Flask FileStorage image to Cloudinary.

    Returns the Cloudinary public_id.
    """

    if not file_storage:
        return None

    if not file_storage.filename:
        return None

    if not is_allowed_image(
        file_storage.filename
    ):
        return None

    if not cloudinary_is_configured():

        raise RuntimeError(
            _configuration_error()
        )


    # --------------------------------------------------------
    # Clean folder name
    # --------------------------------------------------------

    folder = str(
        key_prefix or "uploads"
    ).strip("/")


    # --------------------------------------------------------
    # Upload to Cloudinary
    # --------------------------------------------------------

    result = cloudinary.uploader.upload(
        file_storage.stream,

        folder=folder,

        public_id=uuid.uuid4().hex,

        resource_type="image",

        overwrite=False,

        unique_filename=True,

        use_filename=False,
    )


    # --------------------------------------------------------
    # Return Cloudinary public ID
    # --------------------------------------------------------

    return result.get("public_id")


# ============================================================
# GET PUBLIC URL
# ============================================================

def public_url(key):
    """
    Convert a Cloudinary public_id into a secure URL.
    """

    if not key:
        return None

    if not cloudinary_is_configured():

        raise RuntimeError(
            _configuration_error()
        )

    result = cloudinary.CloudinaryImage(
        key
    ).build_url(
        secure=True
    )

    return result

