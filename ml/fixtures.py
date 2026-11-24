"""Synthetic, self-contained Train/Validation/Test fixture for ML smoke tests.

Writes Train/Validation payload, split audit metadata, and generated PNG images.
Separate synthetic files exercise the post-freeze Test loader. Any score
obtained on these fixtures is a pipeline smoke check only.

    .venv/bin/python -m ml.fixtures --out cache/ml-fixture
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np

# Two overlapping vocabularies make the task learnable but not trivial.
_FAKE_WORDS = ["shocking", "secret", "miracle", "exposed", "hoax", "viral", "banned", "cure"]
_REAL_WORDS = ["senate", "report", "official", "budget", "court", "study", "agency", "vote"]
_SHARED = ["the", "news", "people", "said", "today", "state", "new", "claims", "video", "week"]

FIXTURE_SPLIT_COUNTS = {"train": 14, "validation": 4, "test": 3}  # per label


def _text(rng: np.random.Generator, label: str, n_words: int) -> str:
    own = _FAKE_WORDS if label == "fake" else _REAL_WORDS
    other = _REAL_WORDS if label == "fake" else _FAKE_WORDS
    pool = own * 3 + _SHARED * 2 + other  # mostly own words, some confusion
    return " ".join(rng.choice(pool, size=n_words)).capitalize() + "."


def _png(rng: np.random.Generator, label: str) -> bytes:
    from PIL import Image

    base = np.array([200, 60, 60] if label == "fake" else [60, 90, 200], dtype=np.int16)
    noise = rng.integers(-50, 50, size=(48, 64, 3))
    arr = np.clip(base + noise, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def write_synthetic_dataset(out_dir: Path | str, *, seed: int = 42,
                            counts: dict[str, int] | None = None) -> dict[str, Path]:
    out = Path(out_dir)
    (out / "images").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    group_rng = np.random.default_rng(seed + 1)
    counts = counts or FIXTURE_SPLIT_COUNTS
    rows, assignment = [], []
    for label in ("fake", "real"):
        idx = 0
        for split, n in counts.items():
            for _ in range(n):
                source_id = f"fx-{label}-{idx:03d}"
                sid = f"politifact:{label}:{source_id}"
                group_id = group_rng.bytes(16).hex()
                image_bytes = _png(rng, label)
                rel = f"images/{source_id}.png"
                (out / rel).write_bytes(image_bytes)
                rows.append({
                    "schema_version": "afn-manifest-v1",
                    "is_fixture": True,
                    "sample_id": sid,
                    "source_id": source_id,
                    "source": "politifact",
                    "label": label,
                    "status": "accepted",
                    "publisher": "example.test",
                    "source_url": f"https://example.test/{source_id}",
                    "title": _text(rng, label, 5),
                    "body": _text(rng, label, int(rng.integers(20, 60))),
                    "retrieved_at": "2026-11-23T00:00:00Z",
                    "event_id": None,
                    "group_id": group_id,
                    "exclusion_reason": None,
                    "rights": {"status": "redistributable", "evidence": "Synthetic ML fixture"},
                    "image": {"path": rel, "media_type": "image/png",
                              "sha256": hashlib.sha256(image_bytes).hexdigest()},
                })
                assignment.append((sid, split, group_id))
                idx += 1
    paths = {
        "manifest": out / "manifest.jsonl",
        "split": out / "split.csv",
        "unlocked_manifest": out / "manifest-unlocked.jsonl",
        "unlocked_split": out / "split-unlocked.csv",
        "image_root": out,
    }
    for include_test, manifest, split_path in (
        (False, paths["manifest"], paths["split"]),
        (True, paths["unlocked_manifest"], paths["unlocked_split"]),
    ):
        split_rows = []
        with manifest.open("w", encoding="utf-8") as fh:
            for row, (sid, split, group_id) in zip(rows, assignment, strict=True):
                if include_test or split != "test":
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    split_rows.append((sid, split, group_id))
                else:
                    split_rows.append(("", split, group_id))
        with split_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["sample_id", "split", "group_id"])
            writer.writerows(sorted(split_rows))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    paths = write_synthetic_dataset(args.out, seed=args.seed)
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
