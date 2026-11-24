"""AFN-005 shared preprocessing tests. Synthetic fixtures only, no research data."""

import io
import json
from pathlib import Path

import pytest

from app import preprocessing as pp

FIXTURE = Path(__file__).parent / "fixtures" / "preprocessing" / "afn-preprocess-v1" / "text-cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _body(case):
    if "body_repeat" in case:
        rep = case["body_repeat"]
        return " ".join([rep["word"]] * rep["count"])
    return case["body"]


# --------------------------------------------------------------------- text


def test_fixture_matches_module_version():
    assert CASES["preprocess_version"] == pp.PREPROCESS_VERSION
    assert CASES["synthetic"] is True


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["id"])
def test_text_fixture_cases(case):
    result = pp.preprocess_text(case["title"], _body(case))
    if "expected_text" in case:
        assert result.text == case["expected_text"]
    assert result.truncated is case["expected_truncated"]
    assert result.body_word_count == case["expected_body_word_count"]
    assert result.body_word_count <= pp.MAX_CONTENT_WORDS


@pytest.mark.parametrize("case", CASES["error_cases"], ids=lambda c: c["id"])
def test_text_error_cases(case):
    with pytest.raises(getattr(pp, case["error"])):
        pp.preprocess_text(case["title"], case["body"])


def test_empty_text_is_input_error():
    assert issubclass(pp.EmptyTextError, pp.PreprocessingError)
    assert issubclass(pp.PreprocessingError, ValueError)


def test_api_limit_is_distinct_from_word_cap():
    case = next(c for c in CASES["cases"] if c["id"] == "api_max_chars_not_word_cap")
    body = _body(case)
    assert len(body) <= pp.API_MAX_TEXT_CODE_POINTS  # Backend accepts it
    result = pp.preprocess_text(None, body)
    assert result.truncated is True  # ML still caps it
    assert result.original_body_word_count == 5000
    assert pp.API_MAX_TEXT_CODE_POINTS == 50_000 and pp.MAX_CONTENT_WORDS == 1_500


def test_truncation_keeps_leading_words_in_order():
    body = " ".join(f"w{i}" for i in range(2000))
    result = pp.preprocess_text("T", body)
    assert result.truncated is True
    assert result.body.split() == [f"w{i}" for i in range(1500)]
    assert result.text == "T\n" + result.body


def test_title_does_not_count_towards_word_cap():
    result = pp.preprocess_text("one two three", " ".join(["w"] * 1500))
    assert result.truncated is False
    assert result.title == "one two three"


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["id"])
def test_text_is_deterministic_and_idempotent(case):
    first = pp.preprocess_text(case["title"], _body(case))
    second = pp.preprocess_text(case["title"], _body(case))
    assert first == second
    # Re-normalising already-normalised fields changes nothing.
    again = pp.preprocess_text(first.title, first.body)
    assert again.text == first.text
    assert again.truncated is False


def test_normalize_text_rejects_non_str():
    with pytest.raises(TypeError):
        pp.normalize_text(b"bytes")  # type: ignore[arg-type]


def test_custom_max_words_validated():
    with pytest.raises(ValueError):
        pp.preprocess_text("t", "body", max_words=0)


# -------------------------------------------------------------------- image
# Image/embedding tests need the ML packages (ml/requirements.txt); text tests
# above must still run in a backend-only environment.

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover - backend-only environment
    np = Image = None

needs_ml = pytest.mark.skipif(np is None, reason="Pillow/NumPy not installed")


def _encode(img, fmt="PNG", **kwargs):
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def _asymmetric_rgb(w=6, h=4):
    """Synthetic image whose orientation is detectable (no external assets)."""
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[0, 0] = (255, 0, 0)  # red marks the top-left corner
    arr[:, -1] = (0, 0, 255)  # blue right column
    return Image.fromarray(arr)


@needs_ml
def test_load_png_rgb_roundtrip():
    src = _asymmetric_rgb()
    out = pp.load_image_rgb(_encode(src))
    assert out.mode == "RGB"
    assert np.array_equal(np.asarray(out), np.asarray(src))


@needs_ml
def test_exif_orientation_is_applied():
    src = _asymmetric_rgb()
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 CW to display
    data = _encode(src, "PNG", exif=exif)
    out = pp.load_image_rgb(data)
    expected = src.transpose(Image.Transpose.ROTATE_270)
    assert out.size == (src.height, src.width)
    assert np.array_equal(np.asarray(out), np.asarray(expected))
    assert "exif" not in out.info


@needs_ml
def test_exif_orientation_on_jpeg_changes_size():
    src = Image.new("RGB", (40, 20), (10, 120, 200))
    exif = Image.Exif()
    exif[0x0112] = 8
    out = pp.load_image_rgb(_encode(src, "JPEG", exif=exif, quality=95))
    assert out.size == (20, 40)
    assert out.mode == "RGB"


@needs_ml
def test_alpha_is_flattened_on_white():
    arr = np.zeros((2, 2, 4), dtype=np.uint8)
    arr[..., :3] = (12, 34, 56)  # arbitrary colour under full transparency
    arr[0, 0, 3] = 255  # one opaque pixel
    out = np.asarray(pp.load_image_rgb(_encode(Image.fromarray(arr))))
    assert tuple(out[0, 0]) == (12, 34, 56)
    assert tuple(out[1, 1]) == pp.ALPHA_BACKGROUND_RGB


@needs_ml
def test_palette_with_transparency_and_greyscale_alpha():
    pal = Image.new("P", (3, 3), 0)
    pal.putpalette([0, 0, 0, 200, 10, 10] + [0] * 762)
    pal.putpixel((1, 1), 1)
    out = np.asarray(pp.load_image_rgb(_encode(pal, transparency=0)))
    assert tuple(out[0, 0]) == pp.ALPHA_BACKGROUND_RGB
    assert tuple(out[1, 1]) == (200, 10, 10)

    la = Image.new("LA", (2, 2), (100, 0))
    assert tuple(np.asarray(pp.load_image_rgb(_encode(la)))[0, 0]) == pp.ALPHA_BACKGROUND_RGB


@needs_ml
@pytest.mark.parametrize(
    ("mode", "transparent", "opaque", "opaque_rgb"),
    [
        ("L", 0, 64, (64, 64, 64)),
        ("RGB", (0, 64, 128), (16, 32, 48), (16, 32, 48)),
        ("I;16", 1024, 32768, (128, 128, 128)),
        ("1", 0, 1, (255, 255, 255)),
    ],
)
def test_png_color_key_transparency_is_flattened_on_white(mode, transparent, opaque, opaque_rgb):
    image = Image.new(mode, (2, 1), transparent)
    image.putpixel((1, 0), opaque)

    out = pp.load_image_rgb(_encode(image, transparency=transparent))

    assert out.getpixel((0, 0)) == pp.ALPHA_BACKGROUND_RGB
    assert out.getpixel((1, 0)) == opaque_rgb
    assert "transparency" not in out.info


@needs_ml
@pytest.mark.parametrize(("mode", "colour"), [("L", 0), ("RGB", (0, 64, 128))])
def test_png_color_key_review_fixtures_1x1(mode, colour):
    # Exact PR #68 review fixtures: previously returned (0,0,0) / (0,64,128).
    out = pp.load_image_rgb(_encode(Image.new(mode, (1, 1), colour), transparency=colour))
    assert out.getpixel((0, 0)) == pp.ALPHA_BACKGROUND_RGB


@needs_ml
def test_png_16bit_color_key_matches_wide_value_only():
    # 1000 and 1001 round to the same 8-bit grey; only the exact key is transparent.
    arr = np.array([[1000, 1001]], dtype=np.uint16)
    out = pp.load_image_rgb(_encode(Image.fromarray(arr), transparency=1000))
    assert out.getpixel((0, 0)) == pp.ALPHA_BACKGROUND_RGB
    assert out.getpixel((1, 0)) == (4, 4, 4)


@needs_ml
def test_png_color_key_survives_exif_rotation():
    image = Image.new("RGB", (2, 1), (10, 200, 30))
    image.putpixel((0, 0), (0, 64, 128))
    exif = Image.Exif()
    exif[0x0112] = 6
    out = pp.load_image_rgb(_encode(image, transparency=(0, 64, 128), exif=exif))
    assert out.size == (1, 2)
    assert out.getpixel((0, 0)) == pp.ALPHA_BACKGROUND_RGB
    assert out.getpixel((0, 1)) == (10, 200, 30)


@needs_ml
def test_16bit_png_scaled_to_8bit():
    arr = np.full((2, 2), 65535, dtype=np.uint16)
    img = Image.fromarray(arr)
    out = np.asarray(pp.load_image_rgb(_encode(img)))
    assert out.dtype == np.uint8
    assert tuple(out[0, 0]) == (255, 255, 255)


@needs_ml
def test_same_bytes_same_pixels():
    data = _encode(_asymmetric_rgb(), "JPEG", quality=90)
    a = np.asarray(pp.load_image_rgb(data))
    b = np.asarray(pp.load_image_rgb(data))
    assert np.array_equal(a, b)


@needs_ml
@pytest.mark.parametrize("data", [b"", b"not an image", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20])
def test_invalid_bytes_rejected(data):
    with pytest.raises(pp.InvalidImageError):
        pp.load_image_rgb(data)


@needs_ml
def test_disallowed_format_rejected():
    with pytest.raises(pp.InvalidImageError):
        pp.load_image_rgb(_encode(Image.new("RGB", (2, 2)), "GIF"))


@needs_ml
def test_pixel_limit_checked_before_decode():
    data = _encode(Image.new("RGB", (100, 100)))
    with pytest.raises(pp.InvalidImageError):
        pp.load_image_rgb(data, max_pixels=9_999)
    assert pp.load_image_rgb(data, max_pixels=10_000).size == (100, 100)


# ---------------------------------------------------------------- embedding


@needs_ml
def test_l2_normalize_rows_and_dtype():
    raw = np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float64)
    out = pp.l2_normalize_embeddings(raw, expected_dim=2)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-6)
    assert np.allclose(out[0], [0.6, 0.8])


@needs_ml
def test_l2_normalize_large_finite_values():
    raw = np.array([[1e308, 1e308], [1e308, -1e308]])
    out = pp.l2_normalize_embeddings(raw)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)
    assert np.allclose(out, np.array([[1, 1], [1, -1]]) / np.sqrt(2))


@needs_ml
def test_l2_normalize_1d():
    out = pp.l2_normalize_embeddings([1.0, 0.0, 0.0])
    assert out.shape == (3,) and out.dtype == np.float32


@needs_ml
@pytest.mark.parametrize("bad", [
    [[float("nan"), 1.0]], [[float("inf"), 1.0]], [[-float("inf"), 0.0]], [[0.0, 0.0]], [[1e-20, 0.0]],
])
def test_non_finite_or_zero_embeddings_rejected(bad):
    with pytest.raises(pp.NonFiniteEmbeddingError):
        pp.l2_normalize_embeddings(np.array(bad))


@needs_ml
def test_embedding_shape_errors():
    with pytest.raises(ValueError):
        pp.l2_normalize_embeddings(np.ones((2, 3)), expected_dim=4)
    with pytest.raises(ValueError):
        pp.l2_normalize_embeddings(np.ones((1, 2, 3)))
    with pytest.raises(ValueError):
        pp.l2_normalize_embeddings(np.array([]))


@needs_ml
def test_non_finite_embedding_is_not_input_error():
    # A broken encoder must surface as model failure (503), not user 400.
    assert not issubclass(pp.NonFiniteEmbeddingError, pp.PreprocessingError)
