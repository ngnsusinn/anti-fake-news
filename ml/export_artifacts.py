"""AFN-035: export the three candidate bundles (``afn-model-bundle-v1``).

Trains on Train, selects C/threshold on Validation (same code as
``ml.run_experiments``), writes one pickle-free bundle per configuration plus
``label_map.json``, then reloads every bundle and checks it reproduces the
scikit-learn scores/labels on Validation (export round-trip parity).

    # Fixture bundles for Backend development (#24/#37); NOT research artifacts
    .venv/bin/python -m ml.export_artifacts --fixture --offline

    # Real candidates (#35, after #34 on the audited split)
    .venv/bin/python -m ml.export_artifacts --manifest M.jsonl --split S.csv --image-root DIR --offline

Bundles are ``status: candidate`` until #49 freezes one. Test is never loaded
and no predictions are stored. Output defaults to ``backend/artifacts``
(git-ignored).
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.model_bundle import (
    BUNDLE_DIRS,
    BUNDLE_SCHEMA_VERSION,
    LABEL_MAP_FILE,
    TOKEN_PATTERN,
    load_bundle,
    sha256_bytes,
)
from app.preprocessing import PREPROCESS_VERSION
from ml import REPO_ROOT
from ml.common import (
    Dataset,
    fake_scores,
    labels_to_y,
    load_dataset,
    load_experiment_config,
    order_digest,
    runtime_versions,
    sha256_file,
    tune_on_validation,
)
from ml.extract_embeddings import DEFAULT_EMBEDDING_CACHE, ClipImageEncoder, EmbeddingCache, ImageEncoder
from ml.train_image import build_image_features
from ml.train_multimodal import fuse_features
from ml.train_text import build_text_features, model_texts

DEFAULT_OUT = REPO_ROOT / "backend" / "artifacts"
LABEL_MAP = {"0": "real", "1": "fake"}  # labels_to_y: fake -> 1
PARITY_ATOL = 1e-9


def _write_npy(root: Path, rel: str, arr: np.ndarray, files: dict) -> None:
    import io

    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(arr, dtype=np.float64), allow_pickle=False)
    _write_bytes(root, rel, buf.getvalue(), files)


def _write_bytes(root: Path, rel: str, data: bytes, files: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    files[rel] = {"sha256": sha256_bytes(data), "bytes": len(data)}


def write_bundle(out_root: Path, configuration: str, tune, *, cfg: dict[str, Any], dataset: Dataset,
                 vectorizer=None, encoder_identity: dict[str, str] | None = None,
                 image_dim: int | None = None, inputs: dict[str, str], created_at: str) -> Path:
    model = tune.model
    if [int(c) for c in model.classes_] != [0, 1]:
        raise RuntimeError("unexpected classifier classes_")
    bundle = out_root / BUNDLE_DIRS[configuration]
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)
    files: dict[str, dict] = {}
    _write_npy(bundle, "classifier/coef.npy", model.coef_.reshape(1, -1), files)
    _write_npy(bundle, "classifier/intercept.npy", model.intercept_.reshape(1), files)

    text_meta = image_meta = fusion_meta = None
    text_dim = 0
    if vectorizer is not None:
        vocab = {term: int(idx) for term, idx in sorted(vectorizer.vocabulary_.items(), key=lambda kv: kv[1])}
        _write_bytes(bundle, "text/vocabulary.json",
                     json.dumps(vocab, ensure_ascii=False, sort_keys=True).encode("utf-8"), files)
        _write_npy(bundle, "text/idf.npy", vectorizer.idf_, files)
        tf = cfg["text_features"]
        text_dim = len(vocab)
        text_meta = {"dim": text_dim, "ngram_range": list(tf["ngram_range"]), "lowercase": tf["lowercase"],
                     "token_pattern": TOKEN_PATTERN, "sublinear_tf": tf["sublinear_tf"], "norm": tf["norm"],
                     "max_features": tf["max_features"], "min_df": tf["min_df"], "fit_split": "train"}
    if encoder_identity is not None:
        image_meta = {"dim": int(image_dim), "encoder": dict(encoder_identity), "packaged": False,
                      "weights_note": "CLIP weights are not in this bundle; load the pinned revision "
                                      "from the local Hugging Face cache (configs/clip-reference.json).",
                      "l2_normalized": True}
    if configuration == "multimodal":
        fusion_meta = {"order": list(cfg["fusion"]["order"]), "dtype": cfg["fusion"]["dtype"]}

    feature_dim = int(model.coef_.shape[1])
    if feature_dim != text_dim + (image_dim or 0):
        raise RuntimeError("feature_dim mismatch at export")
    content_hash = sha256_bytes("".join(f["sha256"] for _, f in sorted(files.items())).encode())[:12]
    suffix = "-fixture" if dataset.is_fixture else ""
    train = dataset.rows("train")
    lr = cfg["logistic_regression"]
    metadata = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "configuration": configuration,
        "model_id": f"afn-{configuration}{suffix}",
        "model_version": f"{configuration}-{created_at[:10].replace('-', '')}-{content_hash}{suffix}",
        "status": "candidate",
        "is_fixture": dataset.is_fixture,
        "evidence_kind": "FIXTURE_SMOKE_NOT_RESEARCH" if dataset.is_fixture else "VALIDATION_ONLY",
        "created_at": created_at,
        "preprocess_version": PREPROCESS_VERSION,
        "classes": [0, 1],
        "label_map": LABEL_MAP,
        "positive_label": "fake",
        "threshold": float(tune.best_threshold),
        "threshold_comparison": "greater_than_or_equal",
        "feature_dim": feature_dim,
        "classifier": {"type": "logistic_regression", "C": float(tune.best_c), "solver": lr["solver"],
                       "penalty": "l2", "class_weight": lr["class_weight"], "max_iter": lr["max_iter"],
                       "random_state": lr["random_state"], "n_iter": [int(i) for i in model.n_iter_],
                       "fit_split": "train"},
        "text": text_meta,
        "image": image_meta,
        "fusion": fusion_meta,
        "selection": {"split": "validation", "metric": "macro_f1",
                      "validation_macro_f1": float(tune.best_score),
                      "convergence_warnings_for_C": tune.convergence_warnings},
        "training": {"seed": cfg["seed"], "n_train": len(train),
                     "n_validation": len(dataset.rows("validation")),
                     "train_order_sha256": order_digest([s.sample_id for s in train]),
                     **inputs},
        "versions": runtime_versions(),
        "test_predictions_included": False,
        "files": files,
    }
    (bundle / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    return bundle


def export_all(dataset: Dataset, cfg: dict[str, Any], encoder: ImageEncoder, out_root: Path, *,
               cache: EmbeddingCache | None = None, inputs: dict[str, str]) -> dict[str, Any]:
    if "test" in dataset.splits:
        raise PermissionError("export must not receive Test rows")
    train, val = dataset.rows("train"), dataset.rows("validation")
    positive = cfg["selection"]["positive_label"]
    y_train, y_val = labels_to_y(train, positive), labels_to_y(val, positive)
    text = build_text_features(train, val, cfg)
    emb_train, emb_val = build_image_features(dataset, encoder, cfg, cache)
    dtype = np.dtype(cfg["fusion"]["dtype"])
    blocks = {
        "text-only": (text.X_train, text.X_val),
        "image-only": (emb_train.matrix.astype(dtype), emb_val.matrix.astype(dtype)),
        "multimodal": (
            fuse_features(text.X_train, text.train_ids, emb_train.matrix, emb_train.sample_ids,
                          dtype=cfg["fusion"]["dtype"], order=cfg["fusion"]["order"]),
            fuse_features(text.X_val, text.val_ids, emb_val.matrix, emb_val.sample_ids,
                          dtype=cfg["fusion"]["dtype"], order=cfg["fusion"]["order"]),
        ),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    val_texts, _ = model_texts(val)
    report: dict[str, Any] = {"schema_version": BUNDLE_SCHEMA_VERSION, "created_at": created_at,
                              "is_fixture": dataset.is_fixture, "bundles": {}}
    for name, (X_tr, X_va) in blocks.items():
        tune = tune_on_validation(X_tr, y_train, X_va, y_val, cfg)
        path = write_bundle(
            out_root, name, tune, cfg=cfg, dataset=dataset,
            vectorizer=text.vectorizer if name != "image-only" else None,
            encoder_identity=encoder.identity if name != "text-only" else None,
            image_dim=encoder.dim if name != "text-only" else None,
            inputs=inputs, created_at=created_at)
        # Round-trip parity: reload from disk and score Validation from raw text + embeddings.
        bundle = load_bundle(path, expected_configuration=name)
        X_bundle = bundle.features(val_texts if bundle.uses_text else None,
                                   emb_val.matrix if bundle.uses_image else None)
        ref_scores = fake_scores(tune.model, X_va)
        got = bundle.fake_scores(X_bundle)
        max_diff = float(np.max(np.abs(got - ref_scores)))
        ref_labels = ["fake" if s >= tune.best_threshold else "real" for s in ref_scores]
        labels_equal = bundle.labels(got) == ref_labels
        if max_diff > PARITY_ATOL or not labels_equal:
            raise RuntimeError(f"{name}: exported bundle does not reproduce Validation scores")
        report["bundles"][name] = {"path": BUNDLE_DIRS[name], "model_id": bundle.model_id,
                                   "model_version": bundle.model_version, "feature_dim": X_bundle.shape[1],
                                   "threshold": bundle.threshold, "C": tune.best_c,
                                   "validation_macro_f1": tune.best_score,
                                   "parity": {"n_validation": len(val), "max_abs_score_diff": max_diff,
                                              "atol": PARITY_ATOL, "labels_equal": labels_equal}}
    label_map = {"schema_version": BUNDLE_SCHEMA_VERSION, "classes": LABEL_MAP, "positive_label": "fake"}
    (out_root / LABEL_MAP_FILE).write_text(json.dumps(label_map, indent=2) + "\n", encoding="utf-8")
    (out_root / "export-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--fixture", action="store_true", help="train on the synthetic ML fixture")
    src.add_argument("--manifest", type=Path)
    parser.add_argument("--split", type=Path)
    parser.add_argument("--image-root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_EMBEDDING_CACHE)
    parser.add_argument("--hf-cache-dir", type=Path, default=None)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    if args.fixture:
        from ml.fixtures import write_synthetic_dataset

        paths = write_synthetic_dataset(REPO_ROOT / "cache" / "ml-fixture")
        manifest, split, image_root = paths["manifest"], paths["split"], paths["image_root"]
    else:
        if args.split is None:
            parser.error("--split is required with --manifest")
        manifest, split, image_root = args.manifest, args.split, args.image_root
    config_path = args.config or REPO_ROOT / "configs" / "experiment.yaml"
    cfg = load_experiment_config(config_path)
    dataset = load_dataset(manifest, split, image_root)  # Train + Validation only
    encoder = ClipImageEncoder(REPO_ROOT / cfg["image_features"]["reference"],
                               cache_dir=args.hf_cache_dir, offline=args.offline)
    inputs = {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
              "experiment_config_sha256": sha256_file(config_path)}
    report = export_all(dataset, cfg, encoder, args.out,
                        cache=EmbeddingCache(args.cache_dir, encoder.dim), inputs=inputs)
    kind = "FIXTURE (not research)" if report["is_fixture"] else "candidate"
    print(f"[{kind}] bundles written to {args.out}")
    for name, b in report["bundles"].items():
        print(f"  {name:11s} {b['model_version']}  dim={b['feature_dim']}  thr={b['threshold']:.2f}  "
              f"parity max|diff|={b['parity']['max_abs_score_diff']:.2e} labels_equal={b['parity']['labels_equal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
