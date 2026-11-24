from io import BytesIO
import pytest
from PIL import Image
from conftest import png_bytes
from app import preprocessing
from app.config import IMAGE_MAX_BYTES
from app.errors import InputError
from app.image_validation import validated_image


@pytest.mark.parametrize("mime,body", [("image/jpeg", png_bytes()), ("text/plain", png_bytes()),
                                       (None, png_bytes()), ("image/png", b"bad"),
                                       ("image/png", png_bytes()[:30])])
def test_bad_mime_format_and_decode(mime, body):
    with pytest.raises(InputError) as error:
        with validated_image(body, mime):
            pass
    assert error.value.status == 400


def test_byte_boundary():
    raw = png_bytes()
    at_limit = raw + b"\0" * (IMAGE_MAX_BYTES - len(raw))
    with validated_image(at_limit, "image/png") as rgb:
        assert rgb.mode == "RGB"
    with pytest.raises(InputError) as error:
        with validated_image(at_limit + b"x", "image/png"):
            pass
    assert error.value.status == 413


@pytest.mark.parametrize("size,accepted", [((5000, 4000), True), ((5001, 4000), False)])
def test_real_pixel_boundary(size, accepted):
    data = png_bytes(size, mode="1")
    if accepted:
        with validated_image(data, "image/png") as image:
            assert image.size == size
    else:
        with pytest.raises(InputError):
            with validated_image(data, "image/png"):
                pass


def test_bomb_warning_is_invalid_input(monkeypatch):
    data = png_bytes((11, 10))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(InputError):
        with validated_image(data, "image/png"):
            pass


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P", "L", "RGB", "I;16"])
def test_rgb_matches_shared_ml_helper_and_is_closed(mode):
    kwargs = {"transparency": 0} if mode in ("L", "P", "I;16") else {}
    if mode == "RGB":
        kwargs = {"transparency": (0, 0, 0)}
    data = png_bytes(mode=mode, **kwargs)
    with preprocessing.load_image_rgb(data) as expected:
        with validated_image(data, "image/png") as actual:
            assert actual.mode == "RGB"
            assert actual.tobytes() == expected.tobytes()
    with pytest.raises(ValueError):
        actual.getpixel((0, 0))


def test_exif_rotation_uses_shared_helper():
    with Image.new("RGB", (3, 2)) as original, BytesIO() as stream:
        exif = Image.Exif()
        exif[274] = 6
        original.save(stream, format="JPEG", exif=exif)
        data = stream.getvalue()
    with validated_image(data, "image/jpeg") as rgb:
        assert rgb.size == (2, 3)
        assert "exif" not in rgb.info
