"""Shared preprocessing for offline training and online inference (AFN-005).

One implementation, imported by both ``ml/*`` training scripts and the backend
Predictor, so that the same input always yields the same representation.

Scope (ML-owned, see docs/inference-interface.md):
- Text: Unicode/URL/whitespace/hyphen normalisation, title+body join and the
  1,500-word content cap that sets ``text_truncated``. This is distinct from the
  50,000-code-point transport limit enforced by the Backend before this step.
- Image: decode encoded bytes, apply EXIF orientation, flatten alpha onto a
  fixed background and convert to 8-bit RGB. Model-specific resize/normalise is
  done by the pinned CLIP processor (configs/clip-reference.json), not here.
- Embedding: shared dtype (float32), finiteness checks and row-wise L2 norm.

Text functions use only the standard library so the backend can import this
module without ML packages. Pillow/NumPy are imported lazily by image and
embedding helpers.

Changing any rule below changes model inputs: bump ``PREPROCESS_VERSION``,
retrain/re-extract, and notify Backend/DATA (cache keys and artifact metadata
carry this version).
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    import numpy as np
    from PIL import Image

PREPROCESS_VERSION = "afn-preprocess-v1"

# Transport limits (Backend, docs/api-contract.md) vs. ML content cap.
API_MAX_TEXT_CODE_POINTS = 50_000
API_MAX_TITLE_CODE_POINTS = 500
MAX_CONTENT_WORDS = 1_500

# Image constants shared with Backend #23.
IMAGE_MAX_PIXELS = 20_000_000
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "PNG"})
ALPHA_BACKGROUND_RGB = (255, 255, 255)

EMBEDDING_DTYPE_NAME = "float32"
L2_EPSILON = 1e-12

# Separator between title and body in the joined model text.
TITLE_BODY_SEPARATOR = "\n"


class PreprocessingError(ValueError):
    """Expected, input-related preprocessing failure (Backend maps to 400)."""


class EmptyTextError(PreprocessingError):
    """Body has no words left after normalisation (e.g. only URLs/whitespace)."""


class InvalidImageError(PreprocessingError):
    """Image bytes cannot be decoded as an allowed, size-bounded image."""


class NonFiniteEmbeddingError(ValueError):
    """Embedding contains NaN/Inf or has zero norm; never a user-input error."""


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"(?:https?://|ftp://|www\.)\S+", re.IGNORECASE)
# Invisible characters that silently split or join words.
_INVISIBLE_RE = re.compile("[­​‌‍⁠﻿]")
# Hyphen/dash variants -> ASCII hyphen-minus (stable hyphenation).
_DASH_RE = re.compile("[‐‑‒–—―−﹘﹣－]")
# Word broken across a line: "infor-\n mation" -> "information".
_LINEBREAK_HYPHEN_RE = re.compile(r"(\w)-[ \t]*(?:\r\n|\r|\n)[ \t]*(\w)")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    """Normalise one text field. Deterministic and idempotent.

    Order: NFKC -> drop invisible chars -> unify dashes -> rejoin line-broken
    words -> remove URLs -> collapse whitespace -> strip. Case is preserved;
    lower-casing is the TF-IDF vectoriser's job.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("text fields must be str or None")
    text = unicodedata.normalize("NFKC", value)
    text = _INVISIBLE_RE.sub("", text)
    text = _DASH_RE.sub("-", text)
    text = _LINEBREAK_HYPHEN_RE.sub(r"\1\2", text)
    text = _URL_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def split_words(text: str) -> list[str]:
    """Word definition used for the content cap: whitespace-separated tokens."""
    return text.split()


@dataclass(frozen=True)
class TextPreprocessResult:
    """Model-ready text plus provenance flags."""

    text: str  # title + separator + body; what TF-IDF receives
    title: str
    body: str
    truncated: bool  # becomes PredictionResult.text_truncated
    body_word_count: int  # after truncation
    original_body_word_count: int  # before truncation


def preprocess_text(
    title: str | None, body: str, *, max_words: int = MAX_CONTENT_WORDS
) -> TextPreprocessResult:
    """Normalise title/body, cap the body at ``max_words`` and join them.

    Proposed rule (pending AFN-004 review): the cap counts body words only; the
    title is already bounded (<=500 code points) and is kept whole. An empty or
    missing title contributes nothing. Raises ``EmptyTextError`` if the body
    has no words after normalisation.
    """
    if max_words < 1:
        raise ValueError("max_words must be >= 1")
    norm_title = normalize_text(title)
    words = split_words(normalize_text(body))
    if not words:
        raise EmptyTextError("body is empty after normalisation")
    truncated = len(words) > max_words
    kept = words[:max_words]
    norm_body = " ".join(kept)
    joined = f"{norm_title}{TITLE_BODY_SEPARATOR}{norm_body}" if norm_title else norm_body
    return TextPreprocessResult(
        text=joined,
        title=norm_title,
        body=norm_body,
        truncated=truncated,
        body_word_count=len(kept),
        original_body_word_count=len(words),
    )


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------


def load_image_rgb(image_bytes: bytes, *, max_pixels: int = IMAGE_MAX_PIXELS) -> "Image.Image":
    """Decode JPEG/PNG bytes into an upright 8-bit RGB ``PIL.Image``.

    - Format is detected from content, not filename/MIME.
    - Pixel count is checked from the header *before* full decode.
    - EXIF orientation is applied, then the EXIF data is discarded.
    - Any alpha (RGBA, LA, palette transparency) is composited onto a fixed
      white background so transparent pixels never leak arbitrary colours.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not isinstance(image_bytes, (bytes, bytearray, memoryview)) or len(image_bytes) == 0:
        raise InvalidImageError("image bytes are empty")
    try:
        with Image.open(io.BytesIO(bytes(image_bytes))) as img:
            if img.format not in ALLOWED_IMAGE_FORMATS:
                raise InvalidImageError("unsupported image format")
            width, height = img.size
            if width < 1 or height < 1 or width * height > max_pixels:
                raise InvalidImageError("image pixel count out of range")
            img.load()
            upright = ImageOps.exif_transpose(img)
            return _to_rgb(upright)
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("image cannot be decoded") from exc


def _to_rgb(img: "Image.Image") -> "Image.Image":
    from PIL import Image

    transparency = img.info.get("transparency")
    if transparency is not None and img.mode in ("1", "L", "P", "RGB"):
        img = img.convert("RGBA")
    if img.mode in ("RGBA", "LA", "PA"):
        rgba = img.convert("RGBA")
        background = Image.new("RGBA", rgba.size, ALPHA_BACKGROUND_RGB + (255,))
        img = Image.alpha_composite(background, rgba)
    if img.mode in ("I", "I;16", "I;16B", "I;16L", "F"):
        # 16-bit/float greyscale: scale to 8-bit range before RGB conversion.
        import numpy as np

        arr = np.asarray(img, dtype=np.float64)
        maxv = 65535.0 if img.mode.startswith("I") else (float(arr.max()) or 1.0)
        scaled = np.clip(arr / maxv * 255.0, 0, 255).round().astype(np.uint8)
        if transparency is not None:
            scaled[arr == transparency] = ALPHA_BACKGROUND_RGB[0]
        img = Image.fromarray(scaled)  # 2-D uint8 -> mode "L"
    rgb = img.convert("RGB")
    rgb.info.pop("exif", None)
    rgb.info.pop("transparency", None)
    return rgb


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


def l2_normalize_embeddings(embeddings: Any, *, expected_dim: int | None = None) -> "np.ndarray":
    """Return a float32, row-wise L2-normalised copy of a 1-D or 2-D array.

    Raises ``NonFiniteEmbeddingError`` for NaN/Inf values or (near-)zero rows,
    and ``ValueError`` for wrong rank/dimension. Accepts NumPy arrays or torch
    tensors (converted on CPU).
    """
    import numpy as np

    if hasattr(embeddings, "detach"):  # torch.Tensor without importing torch
        embeddings = embeddings.detach().cpu().numpy()
    arr = np.asarray(embeddings, dtype=np.float64)
    if arr.ndim not in (1, 2) or arr.size == 0:
        raise ValueError("embeddings must be a non-empty 1-D or 2-D array")
    if expected_dim is not None and arr.shape[-1] != expected_dim:
        raise ValueError("embedding dimension mismatch")
    if not np.all(np.isfinite(arr)):
        raise NonFiniteEmbeddingError("embedding contains NaN or Inf")
    # Scaling first avoids overflow when the finite input is squared.
    scale = np.max(np.abs(arr), axis=-1, keepdims=True)
    if np.any(scale == 0):
        raise NonFiniteEmbeddingError("embedding has zero norm")
    scaled = arr / scale
    norms = np.linalg.norm(scaled, axis=-1, keepdims=True)
    if np.any(scale <= L2_EPSILON / norms):
        raise NonFiniteEmbeddingError("embedding has zero norm")
    out = (scaled / norms).astype(np.dtype(EMBEDDING_DTYPE_NAME))
    if not np.all(np.isfinite(out)):
        raise NonFiniteEmbeddingError("normalised embedding is not finite")
    return out
