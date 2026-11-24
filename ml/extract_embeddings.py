"""AFN-020: frozen CLIP image embeddings with a content-addressed cache.

Pipeline per image (identical to inference):
    bytes -> app.preprocessing.load_image_rgb -> pinned CLIPImageProcessor
          -> CLIPModel.get_image_features().pooler_output -> l2_normalize_embeddings

Cache key = sha256(image bytes) + encoder identity (repo, revision, processor
config hash, PREPROCESS_VERSION, dtype). Any change to the image, checkpoint,
processor or preprocessing yields a different key, so stale vectors are never
reused. Cached entries are re-validated (shape, dtype, finite, unit norm).

    .venv/bin/python -m ml.extract_embeddings --manifest M.jsonl --split S.csv \
        --image-root DIR --out cache/embeddings/run.npz [--offline]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

import numpy as np

from app.preprocessing import (
    EMBEDDING_DTYPE_NAME,
    PREPROCESS_VERSION,
    PreprocessingError,
    l2_normalize_embeddings,
    load_image_rgb,
)
from ml import REPO_ROOT
from ml.common import DataContractError, Sample, load_dataset, load_experiment_config

DEFAULT_CLIP_REFERENCE = REPO_ROOT / "configs" / "clip-reference.json"
DEFAULT_EMBEDDING_CACHE = REPO_ROOT / "cache" / "embeddings"


class ImageEncoder(Protocol):
    """Anything that maps RGB PIL images to raw (un-normalised) feature rows."""

    identity: dict[str, str]
    dim: int

    def encode(self, images: list[Any]) -> np.ndarray: ...


class ClipImageEncoder:
    """Pinned, frozen CLIP ViT-B/32 from configs/clip-reference.json (AFN-006)."""

    def __init__(self, reference: Path | str = DEFAULT_CLIP_REFERENCE, *,
                 cache_dir: Path | str | None = None, offline: bool = False) -> None:
        import torch
        from huggingface_hub import snapshot_download
        from transformers import CLIPImageProcessor, CLIPModel

        ref = json.loads(Path(reference).read_text(encoding="utf-8"))
        enc = ref["encoder"]
        runtime = ref["runtime"]
        if cache_dir is None:
            env = os.environ.get(runtime["cache_env"])
            cache_dir = Path(env) / "hub" if env else REPO_ROOT / runtime["default_cache_dir"] / "hub"
        local = snapshot_download(repo_id=enc["repo_id"], revision=enc["revision"],
                                  allow_patterns=enc["files"], cache_dir=str(cache_dir),
                                  local_files_only=offline)
        self._torch = torch
        self.model = CLIPModel.from_pretrained(local, dtype=torch.float32).eval()
        self.model.requires_grad_(False)
        self.processor = CLIPImageProcessor.from_pretrained(local)
        self.dim = int(self.model.config.projection_dim)
        if self.dim != int(ref["embedding"]["dim"]):
            raise DataContractError("CLIP projection_dim differs from clip-reference.json")
        processor_cfg = (Path(local) / "preprocessor_config.json").read_bytes()
        self.identity = {
            "repo_id": enc["repo_id"],
            "revision": enc["revision"],
            "processor_config_sha256": hashlib.sha256(processor_cfg).hexdigest(),
            "preprocess_version": PREPROCESS_VERSION,
            "dtype": EMBEDDING_DTYPE_NAME,
        }

    def encode(self, images: list[Any]) -> np.ndarray:
        inputs = self.processor(images=images, return_tensors="pt")
        with self._torch.inference_mode():
            out = self.model.get_image_features(pixel_values=inputs["pixel_values"])
        feats = out if isinstance(out, self._torch.Tensor) else out.pooler_output
        return feats.detach().cpu().numpy()


def cache_key(image_sha256: str, identity: dict[str, str]) -> str:
    payload = json.dumps({"image_sha256": image_sha256, **identity}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """One ``<key>.npy`` per image; writes are atomic, reads are re-validated."""

    def __init__(self, root: Path | str, dim: int) -> None:
        self.root = Path(root)
        self.dim = dim
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.npy"

    def get(self, key: str) -> np.ndarray | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            vec = np.load(path, allow_pickle=False)
        except (OSError, ValueError):
            return None
        ok = (vec.shape == (self.dim,) and vec.dtype == np.dtype(EMBEDDING_DTYPE_NAME)
              and np.all(np.isfinite(vec)) and abs(float(np.linalg.norm(vec)) - 1.0) < 1e-4)
        return vec if ok else None

    def put(self, key: str, vec: np.ndarray) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                np.save(fh, vec, allow_pickle=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


@dataclass
class EmbeddingSet:
    sample_ids: list[str]
    matrix: np.ndarray  # (n, dim) float32, L2-normalised, row i <-> sample_ids[i]
    identity: dict[str, str]
    stats: dict[str, Any] = field(default_factory=dict)

    def check(self, expected_ids: Sequence[str] | None = None) -> None:
        n, dim = self.matrix.shape
        if n != len(self.sample_ids) or len(set(self.sample_ids)) != n:
            raise DataContractError("embedding rows/sample_ids mismatch or duplicates")
        if self.matrix.dtype != np.dtype(EMBEDDING_DTYPE_NAME):
            raise DataContractError("embedding dtype mismatch")
        if not np.all(np.isfinite(self.matrix)):
            raise DataContractError("non-finite embedding")
        if n and not np.allclose(np.linalg.norm(self.matrix, axis=1), 1.0, atol=1e-4):
            raise DataContractError("embedding rows are not unit norm")
        if expected_ids is not None and list(expected_ids) != self.sample_ids:
            raise DataContractError("embedding sample order differs from expected order")

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, sample_ids=np.array(self.sample_ids), embeddings=self.matrix)
        meta = {"identity": self.identity, "stats": self.stats, "n": len(self.sample_ids),
                "dim": int(self.matrix.shape[1]) if self.matrix.ndim == 2 else 0}
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def _read_image(sample: Sample) -> tuple[bytes, str]:
    if sample.image_path is None:
        raise DataContractError(f"{sample.sample_id}: accepted sample has no image")
    data = sample.image_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if sample.image_sha256 and sample.image_sha256 != digest:
        raise DataContractError(f"{sample.sample_id}: image sha256 differs from manifest")
    return data, digest


def extract_embeddings(samples: Iterable[Sample], encoder: ImageEncoder, *,
                       cache: EmbeddingCache | None = None, batch_size: int = 16) -> EmbeddingSet:
    """Embed every sample's image in input order. Any failure raises with the
    sample_id: accepted samples must have a decodable image (no silent skips)."""
    samples = list(samples)
    vectors: list[np.ndarray | None] = [None] * len(samples)
    pending: list[tuple[int, str, Any]] = []  # (row, key, PIL image)
    hits = 0
    t_start = time.perf_counter()
    encode_seconds = 0.0

    def flush() -> None:
        nonlocal encode_seconds
        if not pending:
            return
        t0 = time.perf_counter()
        raw = encoder.encode([img for _, _, img in pending])
        encode_seconds += time.perf_counter() - t0
        if raw.shape != (len(pending), encoder.dim):
            raise DataContractError("encoder returned unexpected shape")
        normed = l2_normalize_embeddings(raw, expected_dim=encoder.dim)
        for (row, key, _), vec in zip(pending, normed):
            vectors[row] = vec
            if cache is not None:
                cache.put(key, vec)
        pending.clear()

    for row, sample in enumerate(samples):
        data, digest = _read_image(sample)
        key = cache_key(digest, encoder.identity)
        cached = cache.get(key) if cache is not None else None
        if cached is not None:
            vectors[row] = cached
            hits += 1
            continue
        try:
            image = load_image_rgb(data)
        except PreprocessingError as exc:
            raise DataContractError(f"{sample.sample_id}: {exc}") from exc
        pending.append((row, key, image))
        if len(pending) >= batch_size:
            flush()
    flush()

    matrix = (np.vstack(vectors).astype(np.dtype(EMBEDDING_DTYPE_NAME))
              if vectors else np.zeros((0, encoder.dim), dtype=EMBEDDING_DTYPE_NAME))
    encoded = len(samples) - hits
    result = EmbeddingSet(
        sample_ids=[s.sample_id for s in samples],
        matrix=matrix,
        identity=dict(encoder.identity),
        stats={"n": len(samples), "cache_hits": hits, "encoded": encoded,
               "batch_size": batch_size, "total_seconds": round(time.perf_counter() - t_start, 3),
               "encode_seconds": round(encode_seconds, 3),
               "encode_ms_per_image": round(encode_seconds * 1000 / encoded, 1) if encoded else None},
    )
    result.check()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_EMBEDDING_CACHE)
    parser.add_argument("--hf-cache-dir", type=Path, default=None)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    cfg = load_experiment_config(args.config)
    dataset = load_dataset(args.manifest, args.split, args.image_root)
    encoder = ClipImageEncoder(REPO_ROOT / cfg["image_features"]["reference"],
                               cache_dir=args.hf_cache_dir, offline=args.offline)
    cache = EmbeddingCache(args.cache_dir, encoder.dim)
    rows = dataset.rows("train") + dataset.rows("validation")
    emb = extract_embeddings(rows, encoder, cache=cache,
                             batch_size=int(cfg["image_features"]["batch_size"]))
    emb.save(args.out)
    print(json.dumps({"out": str(args.out), "identity": emb.identity, "stats": emb.stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
