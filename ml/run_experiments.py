"""AFN-021: run text-only, image-only and multimodal on the SAME Train/Validation split.

Tuning command only: loads Train + Validation, fits on Train, selects C and
threshold on Validation per configs/experiment.yaml. It never loads Test (the
loader refuses) and has no option to do so; final Test evaluation is a
separate command owned by #50 after the #49 freeze sign-off.

    .venv/bin/python -m ml.run_experiments --manifest M.jsonl --split S.csv \
        --image-root DIR --out-dir cache/runs [--offline]

Writes ``<out-dir>/<run-id>/results.json`` with the config, input hashes,
sample-order hashes, versions, full C x threshold grid and selections.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ml import REPO_ROOT
from ml.common import (
    Dataset,
    load_dataset,
    load_experiment_config,
    runtime_versions,
    sha256_file,
)
from ml.extract_embeddings import (
    DEFAULT_EMBEDDING_CACHE,
    ClipImageEncoder,
    EmbeddingCache,
    ImageEncoder,
)
from ml.train_image import build_image_features, run_image_only
from ml.train_multimodal import run_multimodal
from ml.train_text import build_text_features, run_text_only

ALL_CONFIGS = ("text-only", "image-only", "multimodal")


def run_all(dataset: Dataset, cfg: dict[str, Any], encoder: ImageEncoder | None, *,
            cache: EmbeddingCache | None = None,
            configs: Sequence[str] = ALL_CONFIGS) -> dict[str, Any]:
    unknown = set(configs) - set(ALL_CONFIGS)
    if unknown:
        raise ValueError(f"unknown configurations: {sorted(unknown)}")
    if "test" in dataset.splits:
        raise PermissionError("run_experiments must not receive Test rows")
    train, val = dataset.rows("train"), dataset.rows("validation")
    results: dict[str, Any] = {}
    text = build_text_features(train, val, cfg) if {"text-only", "multimodal"} & set(configs) else None
    emb = None
    if {"image-only", "multimodal"} & set(configs):
        if encoder is None:
            raise ValueError("an image encoder is required for image configurations")
        emb = build_image_features(dataset, encoder, cfg, cache)
    if "text-only" in configs:
        results["text-only"] = run_text_only(dataset, cfg, text)
    if "image-only" in configs:
        results["image-only"] = run_image_only(dataset, cfg, *emb)
    if "multimodal" in configs:
        results["multimodal"] = run_multimodal(dataset, cfg, text, *emb)
    orders = {(r["train_order_sha256"], r["validation_order_sha256"]) for r in results.values()}
    if len(orders) != 1:
        raise RuntimeError("configurations did not use the same split order")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--configs", nargs="+", default=list(ALL_CONFIGS), choices=ALL_CONFIGS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_EMBEDDING_CACHE)
    parser.add_argument("--hf-cache-dir", type=Path, default=None)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "cache" / "runs")
    args = parser.parse_args(argv)

    config_path = args.config or REPO_ROOT / "configs" / "experiment.yaml"
    cfg = load_experiment_config(config_path)
    dataset = load_dataset(args.manifest, args.split, args.image_root)  # Train + Validation only
    encoder = cache = None
    if {"image-only", "multimodal"} & set(args.configs):
        encoder = ClipImageEncoder(REPO_ROOT / cfg["image_features"]["reference"],
                                   cache_dir=args.hf_cache_dir, offline=args.offline)
        cache = EmbeddingCache(args.cache_dir, encoder.dim)
    results = run_all(dataset, cfg, encoder, cache=cache, configs=args.configs)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "run_id": run_id,
        "kind": "train_validation_tuning",
        "evidence_kind": "FIXTURE_SMOKE_NOT_RESEARCH" if dataset.is_fixture else "VALIDATION_ONLY",
        "test_split": {"loaded": False, "locked_rows": dataset.locked_counts.get("test", 0)},
        "inputs": {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
                   "experiment_config_sha256": sha256_file(config_path)},
        "experiment_config": cfg,
        "versions": runtime_versions(),
        "results": results,
    }
    out = args.out_dir / run_id / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[{report['evidence_kind']}] results: {out}")
    for name, r in results.items():
        sel = r["selected"]
        print(f"  {name:11s} dim={r['feature_dim']:5d}  C={sel['C']:<6}  thr={sel['threshold']:.2f}  "
              f"val_macro_f1={sel['validation_macro_f1']:.4f}")
    print(f"  Test: not loaded ({report['test_split']['locked_rows']} rows locked until #49 sign-off)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
