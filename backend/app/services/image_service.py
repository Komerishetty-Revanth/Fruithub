import io

from PIL import Image, ImageOps

from app.core.config import settings
from app.core.errors import AppError

Image.MAX_IMAGE_PIXELS = 40_000_000  # protects against "image bombs"

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MIN_SIDE, MAX_SIDE = 300, 8000
BAD_TYPE = "Only JPG, PNG or WEBP images are allowed."


def load_image(filename: str | None, content_type: str | None, data: bytes) -> Image.Image:
    name = filename or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT or content_type not in ALLOWED_MIME:
        raise AppError("INVALID_FILE_TYPE", BAD_TYPE, 400)
    if len(data) == 0:
        raise AppError("EMPTY_FILE", "The uploaded file is empty.", 400)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError(
            "FILE_TOO_LARGE", f"Image must be smaller than {settings.MAX_UPLOAD_MB} MB.", 413
        )

    try:
        Image.open(io.BytesIO(data)).verify()      # checks the file is a real image
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except Exception:
        raise AppError("INVALID_IMAGE", "This file is not a valid image.", 400)

    if fmt not in ALLOWED_FORMATS:
        raise AppError("INVALID_FILE_TYPE", BAD_TYPE, 400)

    img = ImageOps.exif_transpose(img).convert("RGBA")
    w, h = img.size
    if min(w, h) < MIN_SIDE or max(w, h) > MAX_SIDE:
        raise AppError(
            "INVALID_DIMENSIONS",
            f"Image sides must be between {MIN_SIDE} and {MAX_SIDE} pixels.", 400,
        )

    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])      # transparent areas become white
    background.thumbnail((1600, 1600))
    return background


def encode_webp(img: Image.Image, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=4)
    return buf.getvalue()