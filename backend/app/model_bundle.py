"""Model bundle format ``afn-model-bundle-v1``: pickle-free reader + validator (AFN-035).

Shared by the ML exporter (``ml/export_artifacts.py``) and the Backend loader
(#24) / predictor (#37), like ``preprocessing.py``, so training and serving use
one definition. No pickle/joblib: the bundle is JSON + ``.npy`` arrays loaded
with ``allow_pickle=False``, so loading a bundle can never execute code.

Layout of one bundle directory::

    metadata.json              # schema below; lists every file with sha256
    classifier/coef.npy        # (1, n_features) float64
    classifier/intercept.npy   # (1,) float64
    text/vocabulary.json       # {term: column}   (text-only, multimodal)
    text/idf.npy               # (n_text,) float64 (text-only, multimodal)

CLIP weights are NOT packaged: ``metadata.image.encoder`` pins the reference
(repo/revision/processor hash) and the caller must present an encoder whose
identity matches (``check_encoder_identity``).

Scoring (identical to the scikit-learn objects it was exported from)::

    text  = preprocess_text(title, body).text
    t     = l2_rows(idf * sublinear(count_ngrams(text, vocabulary)))   # TfidfVectorizer
    x     = hstack([t, clip_embedding])          # order from metadata.fusion
    p1    = sigmoid(x @ coef.T + intercept)      # P(classes[1])
    fake_score = p1 if label_map[classes[1]] == "fake" else 1 - p1
    label = "fake" if fake_score >= threshold else "real"
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import numpy as np

from app.preprocessing import PREPROCESS_VERSION, l2_normalize_embeddings, preprocess_text

BUNDLE_SCHEMA_VERSION = "afn-model-bundle-v1"
CONFIGURATIONS = ("text-only", "image-only", "multimodal")
BUNDLE_DIRS = {"text-only": "text_only", "image-only": "image_only", "multimodal": "multimodal"}
LABEL_MAP_FILE = "label_map.json"
FEATURE_DTYPE = np.float64
TOKEN_PATTERN = r"(?u)\b\w\w+\b"  # scikit-learn default, stored explicitly
MAX_ARRAY_BYTES = 64 * 1024 * 1024


class BundleError(RuntimeError):
    """Bundle missing, tampered, or incompatible. Backend maps this to 503
    (model_not_ready); the message never contains paths or file contents."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Prediction:
    label: str
    fake_score: float
    text_truncated: bool
    model_id: str
    model_version: str


class ModelBundle:
    """A validated, immutable bundle ready for inference."""

    def __init__(self, metadata: dict[str, Any], coef: np.ndarray, intercept: np.ndarray,
                 vocabulary: dict[str, int] | None, idf: np.ndarray | None) -> None:
        self.metadata = metadata
        self.configuration: str = metadata["configuration"]
        self.model_id: str = metadata["model_id"]
        self.model_version: str = metadata["model_version"]
        self.threshold: float = float(metadata["threshold"])
        self._coef = coef
        self._intercept = intercept
        self._idf = idf
        self._fake_is_class1 = metadata["label_map"][str(metadata["classes"][1])] == "fake"
        self._counter = None
        if vocabulary is not None:
            from sklearn.feature_extraction.text import CountVectorizer

            text = metadata["text"]
            # Fixed vocabulary -> no fitting ever happens at inference time.
            self._counter = CountVectorizer(
                vocabulary=vocabulary,
                ngram_range=tuple(text["ngram_range"]),
                lowercase=text["lowercase"],
                token_pattern=text["token_pattern"],
                dtype=FEATURE_DTYPE,
            )

    # ------------------------------------------------------------- features

    @property
    def uses_text(self) -> bool:
        return self.metadata["text"] is not None

    @property
    def uses_image(self) -> bool:
        return self.metadata["image"] is not None

    @property
    def image_dim(self) -> int | None:
        return int(self.metadata["image"]["dim"]) if self.uses_image else None

    def text_features(self, texts: list[str]):
        """Exact TfidfVectorizer.transform equivalent (sublinear tf, idf, L2)."""
        from sklearn.preprocessing import normalize

        counts = self._counter.transform(texts).tocsr().astype(FEATURE_DTYPE)
        if self.metadata["text"]["sublinear_tf"]:
            np.log(counts.data, counts.data)
            counts.data += 1.0
        weighted = counts.multiply(self._idf.reshape(1, -1)).tocsr()
        return normalize(weighted, norm=self.metadata["text"]["norm"], copy=False)

    def features(self, texts: list[str] | None, image_embeddings: np.ndarray | None):
        from scipy import sparse

        blocks: dict[str, Any] = {}
        if self.uses_text:
            if texts is None:
                raise ValueError("this bundle requires text")
            blocks["text"] = self.text_features(texts)
        if self.uses_image:
            if image_embeddings is None:
                raise ValueError("this bundle requires an image embedding")
            emb = np.atleast_2d(np.asarray(image_embeddings))
            emb = l2_normalize_embeddings(emb, expected_dim=self.image_dim)
            blocks["image"] = sparse.csr_matrix(emb.astype(FEATURE_DTYPE))
        order = self.metadata["fusion"]["order"] if self.metadata["fusion"] else list(blocks)
        rows = {b.shape[0] for b in blocks.values()}
        if len(rows) != 1:
            raise ValueError("text and image inputs have different row counts")
        X = sparse.hstack([blocks[name] for name in order], format="csr", dtype=FEATURE_DTYPE)
        if X.shape[1] != self._coef.shape[1]:
            raise BundleError("feature dimension does not match classifier")
        return X

    # -------------------------------------------------------------- scoring

    def fake_scores(self, X) -> np.ndarray:
        z = np.asarray(X @ self._coef.T).ravel() + self._intercept[0]
        p1 = 1.0 / (1.0 + np.exp(-z))
        scores = p1 if self._fake_is_class1 else 1.0 - p1
        if not np.all(np.isfinite(scores)):
            raise BundleError("non-finite score")
        return np.clip(scores, 0.0, 1.0)

    def labels(self, scores: np.ndarray) -> list[str]:
        return ["fake" if s >= self.threshold else "real" for s in scores]

    def predict(self, title: str | None, body: str | None,
                image_embedding: np.ndarray | None = None) -> Prediction:
        """One request. ``image_embedding`` = raw or L2 CLIP features of the
        image after ``load_image_rgb`` + the pinned processor (see docs)."""
        truncated = False
        texts = None
        if self.uses_text:
            pre = preprocess_text(title, body or "")
            texts, truncated = [pre.text], pre.truncated
        score = float(self.fake_scores(self.features(texts, image_embedding))[0])
        return Prediction(self.labels(np.array([score]))[0], score, truncated,
                          self.model_id, self.model_version)


# ------------------------------------------------------------------ loading


def _fail(reason: str) -> BundleError:
    return BundleError(f"model bundle rejected: {reason}")


def _read_verified(root: Path, rel: str, expected: dict[str, Any]) -> bytes:
    size = expected["bytes"]
    try:
        path = (root / rel).resolve()
        if root.resolve() not in path.parents:
            raise _fail("file outside bundle")
        if not path.is_file():
            raise _fail("listed file missing")
        with path.open("rb") as handle:
            data = handle.read(size + 1)
    except OSError as exc:
        raise _fail("listed file unreadable") from exc
    if len(data) != size:
        raise _fail("file size mismatch")
    if sha256_bytes(data) != expected["sha256"]:
        raise _fail("checksum mismatch")
    return data


def _load_npy(data: bytes) -> np.ndarray:
    import io

    try:
        arr = np.load(io.BytesIO(data), allow_pickle=False)
    except (ValueError, EOFError, BadZipFile) as exc:
        raise _fail("array is not a plain .npy") from exc
    if isinstance(arr, np.lib.npyio.NpzFile):
        arr.close()
        raise _fail("array is not a plain .npy")
    if arr.dtype != FEATURE_DTYPE or not np.all(np.isfinite(arr)):
        raise _fail("array dtype/finiteness")
    return arr


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _read_json_object(path: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _fail(f"{name} unreadable") from exc
    if not isinstance(value, dict):
        raise _fail(f"{name} is not an object")
    return value


def validate_metadata(meta: dict[str, Any]) -> None:
    """Structural checks that do not need the array files."""
    if meta.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise _fail("schema_version")
    cfg = meta.get("configuration")
    if cfg not in CONFIGURATIONS:
        raise _fail("configuration")
    for key in ("model_id", "model_version"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise _fail(key)
    if meta.get("status") not in ("candidate", "frozen"):
        raise _fail("status")
    if meta.get("test_predictions_included") is not False:
        raise _fail("bundle must not contain Test predictions")
    if meta.get("preprocess_version") != PREPROCESS_VERSION:
        raise _fail("preprocess_version differs from this service")
    classes, label_map = meta.get("classes"), meta.get("label_map")
    if (not isinstance(classes, list) or len(classes) != 2
            or any(type(c) is not int for c in classes) or set(classes) != {0, 1}
            or label_map not in ({"0": "real", "1": "fake"}, {"0": "fake", "1": "real"})):
        raise _fail("classes/label_map")
    if meta.get("positive_label") != "fake" or meta.get("threshold_comparison") != "greater_than_or_equal":
        raise _fail("positive label / threshold rule")
    thr = meta.get("threshold")
    if not isinstance(thr, (int, float)) or isinstance(thr, bool) or not (0.0 < thr < 1.0) or not math.isfinite(thr):
        raise _fail("threshold")
    if not _positive_int(meta.get("feature_dim")):
        raise _fail("feature_dim")
    want_text, want_image = cfg in ("text-only", "multimodal"), cfg in ("image-only", "multimodal")
    if (meta.get("text") is not None) != want_text or (meta.get("image") is not None) != want_image:
        raise _fail("feature blocks do not match configuration")
    if want_text:
        text = meta["text"]
        if not isinstance(text, dict) or not _positive_int(text.get("dim")):
            raise _fail("text feature block")
        ngrams = text.get("ngram_range")
        if (text.get("token_pattern") != TOKEN_PATTERN or text.get("norm") != "l2"
                or not isinstance(text.get("lowercase"), bool)
                or not isinstance(text.get("sublinear_tf"), bool)
                or not isinstance(ngrams, list) or len(ngrams) != 2
                or not all(_positive_int(n) for n in ngrams) or ngrams[0] > ngrams[1]):
            raise _fail("text vectoriser settings")
    if want_image:
        img = meta["image"]
        if not isinstance(img, dict) or not _positive_int(img.get("dim")):
            raise _fail("image feature block")
        enc = img.get("encoder")
        if (not isinstance(enc, dict) or img.get("packaged") is not False
                or img.get("l2_normalized") is not True
                or any(not isinstance(enc.get(k), str) or not enc[k].strip() for k in ("repo_id", "revision"))
                or not _is_sha256(enc.get("processor_config_sha256"))
                or enc.get("preprocess_version") != PREPROCESS_VERSION or enc.get("dtype") != "float32"):
            raise _fail("image encoder reference")
    fusion = meta.get("fusion")
    if cfg == "multimodal":
        if not isinstance(fusion, dict) or fusion.get("order") != ["text", "image"] or fusion.get("dtype") != "float64":
            raise _fail("fusion")
    elif fusion is not None:
        raise _fail("fusion only allowed for multimodal")
    if not isinstance(meta.get("files"), dict) or not meta["files"]:
        raise _fail("files")
    for entry in meta["files"].values():
        if (not isinstance(entry, dict) or not _positive_int(entry.get("bytes"))
                or entry["bytes"] > MAX_ARRAY_BYTES or not _is_sha256(entry.get("sha256"))):
            raise _fail("file size or checksum metadata")


def load_bundle(bundle_dir: Path | str, *, expected_configuration: str | None = None) -> ModelBundle:
    """Load and fully validate one bundle; raises ``BundleError`` on any problem."""
    root = Path(bundle_dir)
    meta = _read_json_object(root / "metadata.json", "metadata.json")
    validate_metadata(meta)
    if expected_configuration and meta["configuration"] != expected_configuration:
        raise _fail("unexpected configuration")
    files = meta["files"]
    needed = {"classifier/coef.npy", "classifier/intercept.npy"}
    if meta["text"] is not None:
        needed |= {"text/vocabulary.json", "text/idf.npy"}
    if set(files) != needed:
        raise _fail("file list")

    coef = _load_npy(_read_verified(root, "classifier/coef.npy", files["classifier/coef.npy"]))
    intercept = _load_npy(_read_verified(root, "classifier/intercept.npy", files["classifier/intercept.npy"]))
    n_features = meta["feature_dim"]
    if coef.shape != (1, n_features) or intercept.shape != (1,):
        raise _fail("classifier shape")

    vocabulary = idf = None
    text_dim = 0
    if meta["text"] is not None:
        try:
            vocabulary = json.loads(_read_verified(root, "text/vocabulary.json",
                                                   files["text/vocabulary.json"]).decode("utf-8"))
        except ValueError as exc:
            raise _fail("vocabulary unreadable") from exc
        idf = _load_npy(_read_verified(root, "text/idf.npy", files["text/idf.npy"]))
        text_dim = meta["text"]["dim"]
        if (not isinstance(vocabulary, dict) or len(vocabulary) != text_dim
                or any(type(index) is not int for index in vocabulary.values())
                or sorted(vocabulary.values()) != list(range(text_dim))
                or idf.shape != (text_dim,) or np.any(idf <= 0)):
            raise _fail("text vocabulary/idf")
    image_dim = meta["image"]["dim"] if meta["image"] is not None else 0
    if text_dim + image_dim != n_features:
        raise _fail("feature_dim != text_dim + image_dim")
    return ModelBundle(meta, coef, intercept, vocabulary, idf)


def check_encoder_identity(bundle: ModelBundle, identity: dict[str, Any], dim: int) -> None:
    """Refuse to pair a bundle with a different CLIP checkpoint/processor/preprocess."""
    if not bundle.uses_image:
        return
    expected = bundle.metadata["image"]["encoder"]
    for key in ("repo_id", "revision", "processor_config_sha256", "preprocess_version", "dtype"):
        if identity.get(key) != expected.get(key):
            raise _fail(f"image encoder {key} differs from bundle")
    if dim != bundle.image_dim:
        raise _fail("image encoder dimension differs from bundle")


def load_label_map(artifacts_root: Path | str) -> dict[str, Any]:
    data = _read_json_object(Path(artifacts_root) / LABEL_MAP_FILE, LABEL_MAP_FILE)
    if data.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise _fail("label_map schema_version")
    if (data.get("classes") not in ({"0": "real", "1": "fake"}, {"0": "fake", "1": "real"})
            or data.get("positive_label") != "fake"):
        raise _fail("label_map classes or positive label")
    return data
