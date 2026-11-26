"""Reproduce the report's aggregate evaluation on the reconstructed ML-v2 holdout."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from ml.common import sha256_file
from ml.evaluate_test import load_test_rows, metrics_for, score
from app.clip_encoder import ClipImageEncoder
from app.model_bundle import load_bundle


ROOT = Path(__file__).resolve().parents[1]


def evaluate(dataset: Path, bundle_root: Path, image_root: Path) -> dict:
    record = json.loads((ROOT / "release/model-freeze.json").read_text(encoding="utf-8"))
    locked_manifest = dataset / "train-validation/manifest.jsonl"
    locked_split = dataset / "train-validation/split.csv"
    holdout_manifest = dataset / "qa-only/manifest-test.jsonl"
    full_split = dataset / "qa-only/split.csv"
    data_hashes = {
        "train_validation_manifest": sha256_file(locked_manifest),
        "masked_split": sha256_file(locked_split),
        "holdout_manifest": sha256_file(holdout_manifest),
        "full_split": sha256_file(full_split),
    }
    if data_hashes["train_validation_manifest"] != record["data"]["manifest_sha256"]:
        raise ValueError("Train/Validation manifest differs from the one used for ML-v2")

    bundles = {}
    model_evidence = {}
    for name, expected in record["configurations"].items():
        directory = bundle_root / Path(expected["bundle_dir"]).name
        metadata_sha256 = sha256_file(directory / "metadata.json")
        bundle = load_bundle(directory, expected_configuration=name, expected_metadata_sha256=metadata_sha256)
        training = bundle.metadata["training"]
        if (
            training["manifest_sha256"] != data_hashes["train_validation_manifest"]
            or training["split_sha256"] != data_hashes["masked_split"]
            or bundle.threshold != expected["threshold"]
            or bundle.metadata["classifier"]["C"] != expected["C"]
            or bundle.metadata["is_fixture"]
        ):
            raise ValueError(f"{name}: unexpected training inputs, settings or fixture bundle")
        for artifact, expected_hash in expected["files_sha256"].items():
            if sha256_file(directory / artifact) != expected_hash:
                raise ValueError(f"{name}: parameter checksum differs for {artifact}")
        bundles[name] = bundle
        model_evidence[name] = {
            "version": bundle.model_version,
            "threshold": bundle.threshold,
            "parameter_files_verified": len(expected["files_sha256"]),
            "metadata_matches_freeze": metadata_sha256 == expected["metadata_sha256"],
            "metadata_sha256": metadata_sha256,
        }

    rows = load_test_rows(
        record, manifest=holdout_manifest, locked_split=locked_split, full_split=full_split, image_root=image_root,
    )
    predictions, truncated = score(bundles, rows, ClipImageEncoder(offline=True))
    metrics = {name: metrics_for(rows, preds) for name, preds in predictions.items()}
    outcomes = {
        (False, False): "both_wrong",
        (False, True): "multimodal_only_correct",
        (True, False): "text_only_correct",
        (True, True): "both_correct",
    }
    support = Counter(row.label for row in rows)
    paired = dict.fromkeys(outcomes.values(), 0)
    for row, text, multimodal in zip(rows, predictions["text-only"], predictions["multimodal"], strict=True):
        paired[outcomes[text[1] == row.label, multimodal[1] == row.label]] += 1

    return {
        "evidence_kind": "EXPLORATORY_REBUILT_HOLDOUT",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n": len(rows),
        "groups": len({row.group_id for row in rows}),
        "support": dict(support),
        "text_truncated": sum(truncated),
        "data_hashes": data_hashes,
        "models": model_evidence,
        "metrics": metrics,
        "delta_macro_f1_mm_minus_text": metrics["multimodal"]["macro_f1"] - metrics["text-only"]["macro_f1"],
        "paired_outcomes": paired,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Local output of ml.prepare_dataset")
    parser.add_argument("--bundle-root", type=Path, default=ROOT / "backend/artifacts")
    parser.add_argument("--image-root", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, required=True, help="Destination for aggregate JSON")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must point to a new file")
    result = evaluate(args.dataset, args.bundle_root, args.image_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f'{result["evidence_kind"]}: {result["n"]} samples, aggregate results in {args.out}')


if __name__ == "__main__":
    main()
