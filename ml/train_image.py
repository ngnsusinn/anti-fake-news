"""AFN-020: Image-only pipeline (frozen CLIP embeddings -> Logistic Regression).

The CLIP encoder is frozen (no fitting); only the classifier is fit, on Train.

    .venv/bin/python -m ml.train_image --manifest M.jsonl --split S.csv \
        --image-root DIR [--offline] [--out result.json]

Scores on fixture data are smoke checks, never research results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from ml import REPO_ROOT
from ml.common import (
    Dataset,
    labels_to_y,
    load_dataset,
    load_experiment_config,
    require_train,
    summarize_result,
    tune_on_validation,
)
from ml.extract_embeddings import (
    DEFAULT_EMBEDDING_CACHE,
    ClipImageEncoder,
    EmbeddingCache,
    EmbeddingSet,
    ImageEncoder,
    extract_embeddings,
)


def build_image_features(dataset: Dataset, encoder: ImageEncoder, cfg: dict[str, Any],
                         cache: EmbeddingCache | None = None) -> tuple[EmbeddingSet, EmbeddingSet]:
    train, val = dataset.rows("train"), dataset.rows("validation")
    require_train(train, "Image-only classifier")
    batch = int(cfg["image_features"]["batch_size"])
    emb_train = extract_embeddings(train, encoder, cache=cache, batch_size=batch)
    emb_val = extract_embeddings(val, encoder, cache=cache, batch_size=batch)
    emb_train.check([s.sample_id for s in train])
    emb_val.check([s.sample_id for s in val])
    return emb_train, emb_val


def run_image_only(dataset: Dataset, cfg: dict[str, Any], emb_train: EmbeddingSet,
                   emb_val: EmbeddingSet) -> dict[str, Any]:
    train, val = dataset.rows("train"), dataset.rows("validation")
    emb_train.check([s.sample_id for s in train])
    emb_val.check([s.sample_id for s in val])
    positive = cfg["selection"]["positive_label"]
    dtype = np.dtype(cfg["fusion"]["dtype"])
    tune = tune_on_validation(emb_train.matrix.astype(dtype), labels_to_y(train, positive),
                              emb_val.matrix.astype(dtype), labels_to_y(val, positive), cfg)
    result = summarize_result("image-only", tune, feature_dim=emb_train.matrix.shape[1],
                              train_ids=emb_train.sample_ids, val_ids=emb_val.sample_ids,
                              is_fixture=dataset.is_fixture)
    result["image"] = {"encoder": emb_train.identity,
                       "train_stats": emb_train.stats, "validation_stats": emb_val.stats}
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
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    cfg = load_experiment_config(args.config)
    dataset = load_dataset(args.manifest, args.split, args.image_root)
    encoder = ClipImageEncoder(REPO_ROOT / cfg["image_features"]["reference"],
                               cache_dir=args.hf_cache_dir, offline=args.offline)
    emb_train, emb_val = build_image_features(dataset, encoder, cfg,
                                              EmbeddingCache(args.cache_dir, encoder.dim))
    result = run_image_only(dataset, cfg, emb_train, emb_val)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
