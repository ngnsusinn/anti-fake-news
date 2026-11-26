"""AFN-050: the single final Test evaluation of the three frozen configurations.

Runs only after AFN-049: the freeze record must carry ML and QA signatures and
``ml.freeze.verify`` must match every pinned hash on disk (config, selection,
code, bundle metadata and arrays). Nothing is fit here: the three bundles are
loaded read-only and score each Test article through ``ModelBundle.predict``,
the same path the Backend serves.

Before Test is read, the QA split is checked against the ID-withheld split
that was frozen: identical Train/Validation assignments, the same number of
Test rows and the same multiset of Test group IDs.

Outputs (one run per protocol; a rerun needs ``--rerun-reason`` and is logged):

* ``test-predictions.jsonl``: one row per Test ``sample_id`` with the source
  label, group and each configuration's ``fake_score``/``label``;
* ``test-metrics.json``: Macro-F1, accuracy, per-class precision/recall/F1/
  support, confusion matrices (rows = true, cols = predicted, ``fake, real``),
  Δ Macro-F1 Multimodal − Text-only, hashes, timestamps and warnings;
* ``confusion-matrices/``: one CSV per configuration and
  ``afn-report-metrics.json`` for ``scripts/summarize_model_results.py``.

    .venv/bin/python -m ml.evaluate_test --freeze release/model-freeze.json \\
        --bundle-root backend/artifacts \\
        --locked-split data/private/ml-v2/train-validation/split.csv \\
        --manifest data/private/ml-v2/qa-only/manifest-test.jsonl \\
        --split data/private/ml-v2/qa-only/split.csv --image-root data --offline --out-dir reports
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from app.model_bundle import BUNDLE_DIRS, ModelBundle, check_encoder_identity, load_bundle
from app.preprocessing import load_image_rgb
from ml import REPO_ROOT
from ml.common import (
    DataContractError, Sample, labels_to_y, load_dataset, load_experiment_config, macro_f1,
    read_split_file, sha256_file, validation_metrics,
)
from ml.freeze import DEFAULT_RECORD, FreezeError, canonical_sha256, read_record, verify

SCHEMA = "afn-test-metrics-v1"
REPORT_SCHEMA = "afn-report-metrics-v1"
LABELS = ["fake", "real"]
PREDICTIONS_FILE = "test-predictions.jsonl"
METRICS_FILE = "test-metrics.json"
MATRIX_DIR = "confusion-matrices"
SMALL_TEST = 100       # below this, one sample moves Macro-F1 by about a point or more
SMALL_SUPPORT = 10     # per-class support below this makes per-class scores unstable


class EvaluationError(RuntimeError):
    """The Test run cannot proceed (split mismatch, image checksum, rerun without reason)."""


# ------------------------------------------------------------------- split


def _test_groups(path: Path) -> Counter:
    with Path(path).open(encoding="utf-8", newline="") as fh:
        return Counter(row["group_id"].strip() for row in csv.DictReader(fh) if row["split"].strip() == "test")


def check_split_against_freeze(record: dict[str, Any], locked_split: Path, full_split: Path) -> dict[str, str]:
    """Return ``{sample_id: group_id}`` for Test after proving it is the frozen Test."""
    if sha256_file(locked_split) != record["data"]["split_sha256"]:
        raise EvaluationError("locked split is not the one in the freeze record")
    hidden, n_locked = read_split_file(locked_split, include_test=False)
    full, _ = read_split_file(full_split, include_test=True)
    visible = {sid: value for sid, value in full.items() if value[0] != "test"}
    if visible != hidden:
        raise EvaluationError("Train/Validation assignments differ between the QA split and the frozen split")
    test = {sid: gid for sid, (split, gid) in full.items() if split == "test"}
    if len(test) != n_locked or n_locked != record["data"]["test_locked_rows"]:
        raise EvaluationError("number of Test rows differs from the freeze record")
    if Counter(test.values()) != _test_groups(locked_split):
        raise EvaluationError("Test group IDs differ from the frozen split")
    return test


def load_test_rows(record: dict[str, Any], *, manifest: Path, locked_split: Path, full_split: Path,
                   image_root: Path | None) -> list[Sample]:
    test = check_split_against_freeze(record, locked_split, full_split)
    with tempfile.TemporaryDirectory(prefix="afn-test-split-") as tmp:
        only_test = Path(tmp) / "split.csv"
        with only_test.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["sample_id", "split", "group_id"])
            for sid in sorted(test):
                writer.writerow([sid, "test", test[sid]])
        dataset = load_dataset(manifest, only_test, image_root, splits=("test",), allow_test=True)
    rows = dataset.rows("test")
    for row in rows:
        if row.image_path is None or row.image_sha256 is None:
            raise EvaluationError(f"Test sample without image: {row.sample_id}")
        if hashlib.sha256(row.image_path.read_bytes()).hexdigest() != row.image_sha256:
            raise EvaluationError(f"image checksum mismatch: {row.sample_id}")
    if not rows:
        raise EvaluationError("no Test rows")
    return rows


# ------------------------------------------------------------------ scoring


def score(bundles: dict[str, ModelBundle], rows: Sequence[Sample], encoder, *,
          batch_size: int = 16) -> tuple[dict[str, list], list[bool]]:
    """Per configuration ``[(fake_score, label), ...]`` in ``rows`` order."""
    embeddings = None
    if any(b.uses_image for b in bundles.values()):
        for bundle in bundles.values():
            check_encoder_identity(bundle, encoder.identity, encoder.dim)
        images = [load_image_rgb(r.image_path.read_bytes()) for r in rows]
        embeddings = np.vstack([np.asarray(encoder.encode(images[i:i + batch_size]))
                                for i in range(0, len(images), batch_size)])
    out: dict[str, list] = {}
    truncated: list[bool] = [False] * len(rows)
    for name, bundle in bundles.items():
        preds = []
        for i, row in enumerate(rows):
            emb = embeddings[i:i + 1] if bundle.uses_image else None
            pred = bundle.predict(row.title, row.body, emb)
            preds.append((pred.fake_score, pred.label))
            if bundle.uses_text:
                truncated[i] = pred.text_truncated
        out[name] = preds
    return out, truncated


def metrics_for(rows: Sequence[Sample], preds: list) -> dict[str, Any]:
    y_true = labels_to_y(rows)
    y_pred = np.array([1 if label == "fake" else 0 for _, label in preds], dtype=np.int64)
    m = validation_metrics(y_true, y_pred)
    return {"macro_f1": macro_f1(y_true, y_pred), "accuracy": m["accuracy"], "per_class": m["per_class"],
            "confusion_matrix": m["confusion_matrix"]}


def warnings_for(rows: Sequence[Sample]) -> list[str]:
    support = Counter(r.label for r in rows)
    out = []
    for label in LABELS:
        if support[label] == 0:
            out.append(f"class '{label}' is missing from Test; its precision/recall/F1 are undefined (reported as 0)")
        elif support[label] < SMALL_SUPPORT:
            out.append(f"class '{label}' has only {support[label]} Test samples; per-class scores are unstable")
    if len(rows) < SMALL_TEST:
        out.append(f"Test has {len(rows)} samples: one sample changes accuracy by {100 / len(rows):.1f} points; "
                   "no statistical significance is claimed for differences between configurations")
    return out


# ------------------------------------------------------------------ outputs


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evaluate(record: dict[str, Any], bundles: dict[str, ModelBundle], rows: Sequence[Sample], encoder, *,
             inputs: dict[str, str], created_at: str, batch_size: int = 16) -> tuple[str, dict, dict]:
    """Return (predictions JSONL text, test-metrics document, report-metrics document)."""
    scores, truncated = score(bundles, rows, encoder, batch_size=batch_size)
    lines = []
    for i, row in enumerate(rows):
        lines.append(json.dumps({
            "sample_id": row.sample_id, "group_id": row.group_id, "source_label": row.label,
            "text_truncated": truncated[i],
            "predictions": {name: {"fake_score": float(scores[name][i][0]), "label": scores[name][i][1],
                                   "model_version": bundles[name].model_version} for name in bundles},
        }, ensure_ascii=False, sort_keys=True))
    predictions = "\n".join(lines) + "\n"

    is_fixture = any(r.is_fixture for r in rows)
    if is_fixture != (record["evidence_kind"] != "VALIDATION_ONLY"):
        raise EvaluationError("fixture Test rows and the freeze evidence kind disagree")
    configs = {}
    for name, bundle in bundles.items():
        frozen = record["configurations"][name]
        configs[name] = {"model_id": bundle.model_id, "model_version": bundle.model_version,
                         "C": frozen["C"], "threshold": bundle.threshold, **metrics_for(rows, scores[name])}
    support = Counter(r.label for r in rows)
    metrics = {
        "schema": SCHEMA,
        "evidence_kind": "FIXTURE_SMOKE_NOT_RESEARCH" if is_fixture else "TEST_FINAL",
        "created_at": created_at,
        "split": "test",
        "labels": LABELS,
        "positive_label": "fake",
        "freeze": {"record_sha256": canonical_sha256(record), "status": record["status"],
                   "signed_by": {role: sig["by"] for role, sig in record["signoffs"].items() if sig}},
        "inputs": {**inputs, "predictions_sha256": _sha256_text(predictions)},
        "n_test": len(rows),
        "n_groups": len({r.group_id for r in rows}),
        "class_support": {label: support[label] for label in LABELS},
        "configurations": configs,
        "delta_macro_f1_mm_minus_text": configs["multimodal"]["macro_f1"] - configs["text-only"]["macro_f1"],
        "warnings": warnings_for(rows),
        "refit": False,
    }
    report = {
        "schema": REPORT_SCHEMA,
        "evidence_kind": "FIXTURE_NOT_RESEARCH" if is_fixture else "TEST_FINAL",
        "labels": LABELS,
        "confusion_matrices": {name: c["confusion_matrix"]["rows_true_cols_pred"] for name, c in configs.items()},
    }
    return predictions, metrics, report


def write_outputs(out_dir: Path, predictions: str, metrics: dict, report: dict, *, rerun_reason: str | None) -> None:
    out_dir = Path(out_dir)
    metrics_path = out_dir / METRICS_FILE
    previous_runs: list[dict] = []
    if (out_dir / PREDICTIONS_FILE).exists() or metrics_path.exists():
        if not rerun_reason or not rerun_reason.strip():
            raise EvaluationError("Test was already evaluated; the protocol allows one run. "
                                  "A rerun for a technical failure needs --rerun-reason")
        if metrics_path.exists():
            previous_runs = json.loads(metrics_path.read_text(encoding="utf-8")).get("runs", [])
    metrics["runs"] = previous_runs + [{
        "created_at": metrics["created_at"], "predictions_sha256": metrics["inputs"]["predictions_sha256"],
        "reason": rerun_reason.strip() if rerun_reason else "first run"}]

    matrix_dir = out_dir / MATRIX_DIR
    matrix_dir.mkdir(parents=True, exist_ok=True)
    for name, cfg in metrics["configurations"].items():
        rows = cfg["confusion_matrix"]["rows_true_cols_pred"]
        text = "true\\pred,fake,real\n" + "".join(f"{label},{r[0]},{r[1]}\n" for label, r in zip(LABELS, rows))
        (matrix_dir / f"{name}.csv").write_text(text, encoding="utf-8")
    (matrix_dir / "afn-report-metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / PREDICTIONS_FILE).write_text(predictions, encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_frozen_bundles(record: dict[str, Any], bundle_root: Path) -> dict[str, ModelBundle]:
    return {name: load_bundle(Path(bundle_root) / BUNDLE_DIRS[name], expected_configuration=name,
                              expected_metadata_sha256=record["configurations"][name]["metadata_sha256"])
            for name in BUNDLE_DIRS}


# --------------------------------------------------------------------- CLI


def run(*, freeze: Path, bundle_root: Path, locked_split: Path, manifest: Path, split: Path,
        image_root: Path | None, out_dir: Path, encoder, root: Path = REPO_ROOT,
        rerun_reason: str | None = None, batch_size: int = 16) -> dict[str, Any]:
    record = verify(read_record(freeze), bundle_root=bundle_root, root=root)  # signed + all hashes match
    rows = load_test_rows(record, manifest=manifest, locked_split=locked_split, full_split=split,
                          image_root=image_root)
    bundles = load_frozen_bundles(record, bundle_root)
    inputs = {"freeze_sha256": sha256_file(freeze), "test_manifest_sha256": sha256_file(manifest),
              "qa_split_sha256": sha256_file(split), "locked_split_sha256": sha256_file(locked_split)}
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    predictions, metrics, report = evaluate(record, bundles, rows, encoder, inputs=inputs,
                                            created_at=created_at, batch_size=batch_size)
    write_outputs(out_dir, predictions, metrics, report, rerun_reason=rerun_reason)
    return metrics


def main(argv: list[str] | None = None) -> int:
    from app.clip_encoder import ClipImageEncoder

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--locked-split", type=Path, required=True, help="frozen split CSV with Test IDs withheld")
    parser.add_argument("--manifest", type=Path, required=True, help="Test-only manifest from QA")
    parser.add_argument("--split", type=Path, required=True, help="QA split CSV with Test IDs")
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    parser.add_argument("--rerun-reason", help="technical failure that forces a rerun (recorded)")
    parser.add_argument("--hf-cache-dir", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_experiment_config()
    try:
        verify(read_record(args.freeze), bundle_root=args.bundle_root)  # fail fast, before loading CLIP
        encoder = ClipImageEncoder(REPO_ROOT / cfg["image_features"]["reference"],
                                   cache_dir=args.hf_cache_dir, offline=args.offline)
        metrics = run(freeze=args.freeze, bundle_root=args.bundle_root, locked_split=args.locked_split,
                      manifest=args.manifest, split=args.split, image_root=args.image_root,
                      out_dir=args.out_dir, encoder=encoder, rerun_reason=args.rerun_reason,
                      batch_size=int(cfg["image_features"]["batch_size"]))
    except (FreezeError, EvaluationError, DataContractError) as exc:
        print(f"TEST NOT EVALUATED: {exc}", file=sys.stderr)
        return 1
    for name, c in metrics["configurations"].items():
        print(f"{name:11s} Macro-F1={c['macro_f1']:.4f} accuracy={c['accuracy']:.4f} "
              f"matrix={c['confusion_matrix']['rows_true_cols_pred']}")
    print(f"Δ Macro-F1 (MM − Text) = {metrics['delta_macro_f1_mm_minus_text']:+.4f}  "
          f"n={metrics['n_test']}  [{metrics['evidence_kind']}]")
    for warning in metrics["warnings"]:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
