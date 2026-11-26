"""AFN-050 final Test command on the synthetic fixture (FakeImageEncoder is a test double).

These tests never touch research data; they prove the gate (signed freeze),
the split check, the no-refit guarantee, the one-run rule and the outputs.
"""

import csv
import json
import subprocess

import numpy as np
import pytest

from app.model_bundle import BUNDLE_DIRS, load_bundle
from ml.common import DEFAULT_EXPERIMENT_CONFIG, load_dataset, sha256_file
from ml.evaluate_test import (
    METRICS_FILE, PREDICTIONS_FILE, RUN_LOCK, EvaluationError, run,
)
from ml.export_artifacts import export_all
from ml.freeze import FreezeError, collect, sign, write_record
from scripts.summarize_model_results import summarize


def _git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.test", *args],
                   cwd=root, check=True, capture_output=True)


@pytest.fixture
def setup(tmp_path, ml_fixture, ml_config, fake_encoder):
    root = tmp_path / "repo"
    (root / "configs").mkdir(parents=True)
    config = root / "configs" / "experiment.yaml"
    config.write_text(DEFAULT_EXPERIMENT_CONFIG.read_text().replace("status: proposed", "status: locked"))
    (root / "ml").mkdir()
    (root / "ml" / "pinned.py").write_text("VALUE = 1\n")
    dataset = load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])
    inputs = {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
              "experiment_config_sha256": sha256_file(config)}
    bundles = root / "artifacts"
    export_all(dataset, ml_config, fake_encoder, bundles, inputs=inputs)
    chosen = {}
    for name, folder in BUNDLE_DIRS.items():
        meta = json.loads((bundles / folder / "metadata.json").read_text())
        chosen[name] = {"C": meta["classifier"]["C"], "threshold": meta["threshold"]}
    selected = root / "configs" / "selected-models.json"
    selected.write_text(json.dumps({"selection_split": "validation", "inputs": inputs,
                                    "test_split": {"loaded": False}, "configurations": chosen}))
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    record = collect(bundle_root=bundles, manifest=ml_fixture["manifest"], split=ml_fixture["split"],
                     selected_path=selected, config_path=config, root=root, code_files=("ml/pinned.py",),
                     allow_fixture=True)
    assert record["blockers"] == []
    freeze = root / "release" / "model-freeze.json"
    write_record(record, freeze)

    # QA package: Test-only manifest + full split.
    with open(ml_fixture["unlocked_split"], newline="") as fh:
        test_ids = {r["sample_id"] for r in csv.DictReader(fh) if r["split"] == "test"}
    test_manifest = tmp_path / "qa" / "manifest-test.jsonl"
    test_manifest.parent.mkdir()
    lines = [line for line in open(ml_fixture["unlocked_manifest"]) if json.loads(line)["sample_id"] in test_ids]
    test_manifest.write_text("".join(lines))
    args = dict(freeze=freeze, bundle_root=bundles, locked_manifest=ml_fixture["manifest"],
                locked_split=ml_fixture["split"], manifest=test_manifest,
                split=ml_fixture["unlocked_split"], image_root=ml_fixture["image_root"],
                out_dir=tmp_path / "reports", encoder=fake_encoder, root=root)
    return args, record, test_ids


def _sign(args, record):
    write_record(sign(sign(record, "ml", "ml-person"), "qa", "qa-person"), args["freeze"])


def test_unsigned_freeze_never_reads_test(setup, monkeypatch):
    args, _, _ = setup
    monkeypatch.setattr("ml.evaluate_test.load_test_rows",
                        lambda *a, **k: pytest.fail("Test was read before the freeze was signed"))
    with pytest.raises(FreezeError, match="missing ml signature"):
        run(**args)
    assert not args["out_dir"].exists()


def test_signed_run_writes_predictions_and_metrics(setup):
    args, record, test_ids = setup
    _sign(args, record)
    metrics = run(**args)
    out = args["out_dir"]
    rows = [json.loads(line) for line in (out / PREDICTIONS_FILE).read_text().splitlines()]
    assert [r["sample_id"] for r in rows] == sorted(test_ids)
    assert all(set(r["predictions"]) == set(BUNDLE_DIRS) for r in rows)
    assert {r["source_label"] for r in rows} <= {"fake", "real"}

    # Scores are exactly what the frozen bundle serves.
    text = load_bundle(args["bundle_root"] / "text_only")
    dataset = {json.loads(line)["sample_id"]: json.loads(line) for line in args["manifest"].open()}
    first = dataset[rows[0]["sample_id"]]
    assert rows[0]["predictions"]["text-only"]["fake_score"] == text.predict(first["title"], first["body"]).fake_score

    assert metrics["evidence_kind"] == "FIXTURE_SMOKE_NOT_RESEARCH" and metrics["refit"] is False
    assert metrics["n_test"] == len(test_ids) == sum(metrics["class_support"].values())
    assert metrics["freeze"]["status"] == "signed"
    assert metrics["freeze"]["signed_by"] == {"ml": "ml-person", "qa": "qa-person"}
    assert metrics["inputs"]["predictions_sha256"] == sha256_file(out / PREDICTIONS_FILE)
    assert any("no statistical significance" in w for w in metrics["warnings"])
    assert json.loads((out / METRICS_FILE).read_text())["runs"][0]["reason"] == "first run"

    # Integration's report script recomputes the same numbers from the matrices.
    report = json.loads((out / "confusion-matrices" / "afn-report-metrics.json").read_text())
    summary = summarize(report)
    for name, cfg in metrics["configurations"].items():
        assert summary["configurations"][name]["macro_f1"] == pytest.approx(cfg["macro_f1"])
        assert summary["configurations"][name]["accuracy"] == pytest.approx(cfg["accuracy"])
        assert cfg["confusion_matrix"]["labels"] == ["fake", "real"]
    assert summary["delta_macro_f1_mm_minus_text"] == pytest.approx(metrics["delta_macro_f1_mm_minus_text"])
    assert (out / "confusion-matrices" / "multimodal.csv").read_text().startswith("true\\pred,fake,real\n")


def test_nothing_is_fit_during_evaluation(setup, monkeypatch):
    args, record, _ = setup
    _sign(args, record)

    def no_fit(*a, **k):
        raise AssertionError("evaluation must not fit")

    monkeypatch.setattr("sklearn.linear_model.LogisticRegression.fit", no_fit)
    monkeypatch.setattr("sklearn.feature_extraction.text.TfidfVectorizer.fit", no_fit)
    monkeypatch.setattr("sklearn.feature_extraction.text.TfidfVectorizer.fit_transform", no_fit)
    run(**args)


def test_second_run_needs_a_recorded_reason(setup, monkeypatch):
    args, record, _ = setup
    _sign(args, record)
    run(**args)
    with monkeypatch.context() as guard:
        guard.setattr("ml.evaluate_test.load_test_rows",
                      lambda *a, **k: pytest.fail("rerun read Test without authorization"))
        with pytest.raises(EvaluationError, match="one run"):
            run(**args, rerun_reason=" ")
    run(**args, rerun_reason="process killed while writing outputs")
    runs = json.loads((args["out_dir"] / METRICS_FILE).read_text())["runs"]
    assert [r["reason"] for r in runs] == ["first run", "process killed while writing outputs"]


def test_failed_scoring_needs_a_reason_to_retry(setup, monkeypatch):
    args, record, _ = setup
    _sign(args, record)

    def fail_scoring(*args, **kwargs):
        raise RuntimeError("encoder failed")

    with monkeypatch.context() as scoring:
        scoring.setattr("ml.evaluate_test.score", fail_scoring)
        with pytest.raises(RuntimeError, match="encoder failed"):
            run(**args)
    assert not (args["out_dir"] / METRICS_FILE).exists()
    with pytest.raises(EvaluationError, match="one run"):
        run(**args)
    metrics = run(**args, rerun_reason="encoder failed")
    assert metrics["runs"][0]["reason"] == "encoder failed"


def test_concurrent_run_cannot_read_test(setup, monkeypatch):
    args, record, _ = setup
    _sign(args, record)
    (args["out_dir"] / RUN_LOCK).mkdir(parents=True)
    monkeypatch.setattr("ml.evaluate_test.load_test_rows",
                        lambda *a, **k: pytest.fail("concurrent run tried to read Test"))
    with pytest.raises(EvaluationError, match="locked by an evaluation"):
        run(**args, rerun_reason="technical failure")


@pytest.mark.parametrize(("path_key", "message"), [
    ("locked_manifest", "Train/Validation manifest changed"),
    ("locked_split", "split CSV with Test IDs withheld changed"),
])
def test_changed_handover_blocks_test_read(setup, monkeypatch, path_key, message):
    args, record, _ = setup
    _sign(args, record)
    with args[path_key].open("ab") as file:
        file.write(b"\n")
    monkeypatch.setattr("ml.evaluate_test.load_test_rows",
                        lambda *a, **k: pytest.fail("Test was read before verifying the handover"))
    with pytest.raises(FreezeError, match=message):
        run(**args)


def _rewrite_split(path, out, mutate):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    mutate(rows)
    with open(out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["sample_id", "split", "group_id"])
        writer.writeheader()
        writer.writerows(rows)
    return out


@pytest.mark.parametrize("change", ["train_row_moved_to_test", "test_group_renamed"])
def test_qa_split_must_match_frozen_split(setup, tmp_path, change):
    args, record, _ = setup
    _sign(args, record)

    def mutate(rows):
        if change == "train_row_moved_to_test":
            row = next(r for r in rows if r["split"] == "train")
            row["split"] = "test"
            row["group_id"] = "new-group"
        else:
            row = next(r for r in rows if r["split"] == "test")
            row["group_id"] = "renamed"

    args["split"] = _rewrite_split(args["split"], tmp_path / "qa-split.csv", mutate)
    with pytest.raises(EvaluationError):
        run(**args)
    assert not (args["out_dir"] / PREDICTIONS_FILE).exists()
    assert not (args["out_dir"] / METRICS_FILE).exists()


def test_image_checksum_is_checked(setup):
    args, record, _ = setup
    _sign(args, record)
    first = json.loads(args["manifest"].read_text().splitlines()[0])
    (args["image_root"] / first["image"]["path"]).write_bytes(b"not the frozen image")
    with pytest.raises(EvaluationError, match="checksum"):
        run(**args)


def test_bundle_changed_after_signing_is_refused(setup):
    args, record, _ = setup
    _sign(args, record)
    coef = args["bundle_root"] / "image_only" / "classifier" / "coef.npy"
    arr = np.load(coef)
    arr[0, 0] += 1.0
    np.save(coef, arr)
    with pytest.raises(FreezeError):
        run(**args)
