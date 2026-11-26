"""Audit saved AFN-050 predictions, without loading a model or reading articles."""

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from math import isclose
from pathlib import Path

if __package__:
    from .summarize_model_results import CONFIGURATIONS, LABELS, SCHEMA, summarize
else:
    from summarize_model_results import CONFIGURATIONS, LABELS, SCHEMA, summarize


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def utc_time(value):
    timestamp = datetime.fromisoformat(value)
    require(timestamp.utcoffset() is not None, "timestamps must include a timezone")
    return timestamp


def audit(freeze_path, metrics_path, predictions_path, locked_split, qa_split):
    freeze_bytes = freeze_path.read_bytes()
    freeze = json.loads(freeze_bytes)
    chosen = freeze["configurations"]
    require(
        freeze["schema"] == "afn-model-freeze-v1" and freeze["status"] == "signed"
        and freeze["evidence_kind"] == "VALIDATION_ONLY" and freeze["blockers"] == []
        and freeze["protocol"]["status"] == "locked"
        and freeze["protocol"]["refit_on_train_and_validation"] is False
        and freeze["label_map"] == {"0": "real", "1": "fake"}
        and set(chosen) == set(CONFIGURATIONS),
        "expected a signed research freeze with the locked label map",
    )
    body = {key: value for key, value in freeze.items() if key not in ("status", "signoffs")}
    record_digest = digest(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    signatures = {role: freeze["signoffs"][role] for role in ("ml", "qa")}
    signed_by = {role: signature["by"].strip() for role, signature in signatures.items()}
    require(all(signed_by.values()) and len({name.casefold() for name in signed_by.values()}) == 2,
            "two distinct signers are required")
    frozen_at = utc_time(freeze["created_at"])
    signed_at = {utc_time(signature["at"]) for signature in signatures.values()}
    require(all(signature["record_sha256"] == record_digest for signature in signatures.values())
            and min(signed_at) >= frozen_at, "signatures must correspond to this freeze and follow its creation")

    metrics = json.loads(metrics_path.read_bytes())
    require(
        metrics["schema"] == "afn-test-metrics-v1" and metrics["evidence_kind"] == "TEST_FINAL"
        and metrics["split"] == "test" and metrics["refit"] is False
        and metrics["labels"] == list(LABELS) and metrics["positive_label"] == "fake"
        and metrics["freeze"] == {"record_sha256": record_digest, "status": "signed", "signed_by": signed_by}
        and set(metrics["configurations"]) == set(CONFIGURATIONS),
        "metrics must describe final Test for the signed freeze",
    )
    prediction_bytes = predictions_path.read_bytes()
    locked_bytes = locked_split.read_bytes()
    qa_bytes = qa_split.read_bytes()
    inputs = metrics["inputs"]
    require(inputs["freeze_sha256"] == digest(freeze_bytes)
            and inputs["predictions_sha256"] == digest(prediction_bytes)
            and inputs["qa_split_sha256"] == digest(qa_bytes)
            and inputs["locked_split_sha256"] == digest(locked_bytes) == freeze["data"]["split_sha256"],
            "input checksums do not match the evaluation and freeze")
    runs = metrics["runs"]
    dates = [utc_time(run["created_at"]) for run in runs]
    require(dates and dates == sorted(dates) and min(dates) >= max(signed_at)
            and runs[-1]["created_at"] == metrics["created_at"]
            and runs[-1]["predictions_sha256"] == inputs["predictions_sha256"],
            "run log must follow both signoffs and identify the evaluated predictions")
    for index, run in enumerate(runs):
        reason = run["reason"].strip()
        require(reason and (index == 0 or reason != "first run")
                and len(run["predictions_sha256"]) == 64
                and all(char in "0123456789abcdef" for char in run["predictions_sha256"]),
                "each run must record a reason and predictions checksum")

    def read_split(raw, *, hidden):
        visible, test_groups, group_splits = {}, Counter(), {}
        reader = csv.DictReader(raw.decode("utf-8").splitlines())
        fields = ("sample_id", "split", "group_id")
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(fields)
                and set(reader.fieldnames) == set(fields), "invalid split header")
        for row in reader:
            require(None not in row and None not in row.values(), "invalid split columns")
            sample, split, group = (row[key].strip() for key in ("sample_id", "split", "group_id"))
            require(group and split in {"train", "validation", "test"}, "invalid split row")
            require(group_splits.setdefault(group, split) == split, "a group spans several splits")
            if hidden and split == "test":
                require(not sample, "locked split must withhold Test IDs")
                test_groups[group] += 1
                continue
            require(sample and sample not in visible, "expected unique split IDs")
            visible[sample] = (split, group)
        return visible, test_groups

    public_rows, locked_groups = read_split(locked_bytes, hidden=True)
    qa_rows, _ = read_split(qa_bytes, hidden=False)
    test = {sample: group for sample, (split, group) in qa_rows.items() if split == "test"}
    require(test and public_rows == {sample: pair for sample, pair in qa_rows.items() if pair[0] != "test"}
            and Counter(test.values()) == locked_groups and len(test) == freeze["data"]["test_locked_rows"],
            "QA split disagrees with the frozen assignments or Test groups")

    matrices = {name: [[0, 0], [0, 0]] for name in CONFIGURATIONS}
    labels = {label: index for index, label in enumerate(LABELS)}
    for name, config in chosen.items():
        observed = metrics["configurations"][name]
        require(config["is_fixture"] is False and all(
            observed[key] == config[key] for key in ("model_id", "model_version", "C", "threshold")
        ), "configuration differs from the frozen model")
    seen, support = set(), Counter()
    for line in prediction_bytes.decode("utf-8").splitlines():
        row = json.loads(line)
        sample, label = row["sample_id"], row["source_label"]
        require(sample not in seen and sample in test and row["group_id"] == test[sample]
                and label in labels and set(row["predictions"]) == set(CONFIGURATIONS),
                "invalid prediction row or Test ID/group mismatch")
        seen.add(sample)
        support[label] += 1
        for name, prediction in row["predictions"].items():
            config = chosen[name]
            score = prediction["fake_score"]
            require(type(score) in (int, float) and 0 <= score <= 1, "prediction score outside [0, 1]")
            predicted = "fake" if score >= config["threshold"] else "real"
            require(prediction["label"] == predicted and prediction["model_version"] == config["model_version"],
                    "predicted label or model version disagrees with freeze")
            matrices[name][labels[label]][labels[predicted]] += 1
    require(seen == test.keys() and metrics["n_test"] == len(seen) and metrics["n_groups"] == len(locked_groups)
            and metrics["class_support"] == {label: support[label] for label in LABELS},
            "prediction coverage or class support does not match evaluation")

    result = summarize({"schema": SCHEMA, "evidence_kind": "TEST_FINAL", "labels": list(LABELS),
                        "confusion_matrices": matrices})

    def compare(actual, reported):
        require(type(reported) in (float, int) and isclose(actual, reported, rel_tol=0, abs_tol=1e-12),
                "reported score does not match predictions")

    for name, actual in result["configurations"].items():
        reported = metrics["configurations"][name]
        require(reported["confusion_matrix"] == {
            "labels": list(LABELS), "rows_true_cols_pred": actual["rows_true_cols_pred"]
        }, "confusion matrix does not match predictions")
        for key in ("macro_f1", "accuracy"):
            compare(actual[key], reported[key])
        for label in LABELS:
            expected_class = actual["per_class"][label]
            reported_class = reported["per_class"][label]
            require(expected_class["support"] == reported_class["support"], "reported class support differs")
            for key in ("precision", "recall", "f1"):
                compare(expected_class[key], reported_class[key])
    compare(result["delta_macro_f1_mm_minus_text"], metrics["delta_macro_f1_mm_minus_text"])
    return {"status": "PASS", "record_sha256": record_digest, "predictions_sha256": inputs["predictions_sha256"],
            "n_test": len(seen), "n_groups": len(locked_groups), **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("freeze", "metrics", "predictions", "locked-split", "qa-split"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.freeze, args.metrics, args.predictions, args.locked_split, args.qa_split)
    except (KeyError, AttributeError, TypeError, OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"BLOCKED: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
