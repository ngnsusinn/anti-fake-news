"""AFN-023: verify transport image, then call the unchanged ML image helper."""

from contextlib import contextmanager
from io import BytesIO
from typing import Iterator
import warnings

from PIL import Image, UnidentifiedImageError

from app import preprocessing
from app.config import IMAGE_MAX_BYTES, IMAGE_MAX_PIXELS
from app.errors import InputError

MIME_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG"}


@contextmanager
def validated_image(image_bytes: bytes, content_type: str | None) -> Iterator[Image.Image]:
    """Yield an owned RGB image; close it on all exits. Never log decoder errors."""
    if len(image_bytes) > IMAGE_MAX_BYTES:
        raise InputError(status=413)
    expected = MIME_FORMATS.get(content_type or "")
    if expected is None or not image_bytes:
        raise InputError
    rgb = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with BytesIO(image_bytes) as stream, Image.open(stream) as image:
                if image.format != expected or image.width * image.height > IMAGE_MAX_PIXELS:
                    raise InputError
                image.verify()
            rgb = preprocessing.load_image_rgb(image_bytes, max_pixels=IMAGE_MAX_PIXELS)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        if rgb is not None:
            rgb.close()
        raise InputError from None
    try:
        yield rgb
    finally:
        rgb.close()


def validate_image_bytes(image_bytes: bytes, content_type: str | None) -> None:
    # Preserve the encoded-bytes Predictor seam. #37 can use the same helper
    # for its RGB tensor inputs; no second EXIF/alpha implementation exists.
    with validated_image(image_bytes, content_type):
        pass
