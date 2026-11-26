"""AFN-049 freeze record: collect, sign, verify (synthetic fixture; FakeImageEncoder is a test double)."""

import json
import subprocess
from shutil import copyfile

import numpy as np
import pytest

from app.model_bundle import BUNDLE_DIRS
from ml.common import DEFAULT_EXPERIMENT_CONFIG, load_dataset, sha256_file
from ml.export_artifacts import export_all
from ml.freeze import FreezeError, canonical_sha256, collect, main, sign, verify

CODE = ("ml/pinned.py",)


def _git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.test", *args],
                   cwd=root, check=True, capture_output=True)


def _write_config(root, status):
    text = DEFAULT_EXPERIMENT_CONFIG.read_text(encoding="utf-8").replace("status: proposed", f"status: {status}")
    path = root / "configs" / "experiment.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def frozen_inputs(tmp_path, ml_fixture, ml_config, fake_encoder):
    root = tmp_path / "repo"
    config = _write_config(root, "locked")
    (root / "ml").mkdir()
    (root / "ml" / "pinned.py").write_text("VALUE = 1\n")
    dataset = load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])
    inputs = {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
              "experiment_config_sha256": sha256_file(config)}
    bundles = root / "artifacts"
    export_all(dataset, ml_config, fake_encoder, bundles, inputs=inputs)
    configurations = {}
    for name, folder in BUNDLE_DIRS.items():
        meta = json.loads((bundles / folder / "metadata.json").read_text())
        configurations[name] = {"C": meta["classifier"]["C"], "threshold": meta["threshold"]}
    selected = root / "configs" / "selected-models.json"
    selected.write_text(json.dumps({"schema": "afn-selected-models-v1", "status": "candidate",
                                    "selection_split": "validation", "inputs": inputs,
                                    "test_split": {"loaded": False, "locked_rows": 6},
                                    "configurations": configurations}))
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    kwargs = dict(bundle_root=bundles, manifest=ml_fixture["manifest"], split=ml_fixture["split"],
                  selected_path=selected, config_path=config, root=root, code_files=CODE,
                  allow_fixture=True)
    return root, kwargs


def test_collect_pins_hashes_without_test(frozen_inputs, ml_fixture):
    root, kwargs = frozen_inputs
    record = collect(**kwargs)
    assert record["status"] == "draft" and record["blockers"] == []
    assert record["evidence_kind"] == "FIXTURE_SMOKE_NOT_RESEARCH"
    assert record["data"]["test_locked_rows"] > 0
    assert record["data"]["manifest_sha256"] == sha256_file(ml_fixture["manifest"])
    assert set(record["configurations"]) == set(BUNDLE_DIRS)
    mm = record["configurations"]["multimodal"]
    assert mm["metadata_sha256"] == sha256_file(root / "artifacts" / "multimodal" / "metadata.json")
    assert set(mm["files_sha256"]) == {"classifier/coef.npy", "classifier/intercept.npy",
                                       "text/idf.npy", "text/vocabulary.json"}
    assert record["code"]["uncommitted_changes"] is False and record["code"]["git_commit"]
    assert record["label_map"] == {"0": "real", "1": "fake"}
    assert record["signoffs"] == {"ml": None, "qa": None}


def test_soft_gaps_become_blockers_and_block_signing(frozen_inputs):
    root, kwargs = frozen_inputs
    kwargs["config_path"] = _write_config(root, "proposed")
    with pytest.raises(FreezeError, match="experiment_config_sha256"):
        collect(**kwargs)  # selection was made under the locked config hash

    _write_config(root, "locked")
    (root / "ml" / "pinned.py").write_text("VALUE = 2\n")
    record = collect(**dict(kwargs, allow_fixture=False))
    assert any("uncommitted" in b for b in record["blockers"])
    assert any("fixture" in b for b in record["blockers"])
    with pytest.raises(FreezeError, match="blockers"):
        sign(record, "ml", "someone")


def test_inconsistent_selection_is_refused(frozen_inputs):
    root, kwargs = frozen_inputs
    selected = json.loads(kwargs["selected_path"].read_text())
    selected["configurations"]["text-only"]["threshold"] = 0.123
    kwargs["selected_path"].write_text(json.dumps(selected))
    with pytest.raises(FreezeError, match="text-only: bundle C/threshold"):
        collect(**kwargs)


def test_two_signatures_then_verify(frozen_inputs):
    root, kwargs = frozen_inputs
    record = collect(**kwargs)
    handover = root / "data" / "private" / "ml-v2" / "train-validation"
    handover.mkdir(parents=True)
    copyfile(kwargs["manifest"], handover / "manifest.jsonl")
    copyfile(kwargs["split"], handover / "split.csv")
    with pytest.raises(FreezeError, match="missing ml signature"):
        verify(record, bundle_root=kwargs["bundle_root"], root=root)
    sign(record, "ml", "ml-person")
    assert record["status"] == "draft"
    sign(record, "qa", "qa-person", note="audit + parity checked")
    assert record["status"] == "signed"
    assert record["signoffs"]["qa"]["record_sha256"] == canonical_sha256(record)
    verify(record, bundle_root=kwargs["bundle_root"], root=root)


def test_edit_after_signing_voids_signatures(frozen_inputs):
    root, kwargs = frozen_inputs
    record = sign(sign(collect(**kwargs), "ml", "a"), "qa", "b")
    record["configurations"]["multimodal"]["threshold"] = 0.3
    with pytest.raises(FreezeError, match="edited after signing"):
        verify(record, bundle_root=kwargs["bundle_root"], root=root,
               manifest=kwargs["manifest"], split=kwargs["split"])


@pytest.mark.parametrize(("target", "message"), [
    ("coef", "bundle does not match"),
    ("code", "pinned code changed"),
    ("config", "experiment config changed"),
    ("manifest", "Train/Validation manifest changed"),
    ("split", "split CSV with Test IDs withheld changed"),
])
def test_changed_files_after_freeze_fail_verify(frozen_inputs, target, message):
    root, kwargs = frozen_inputs
    record = sign(sign(collect(**kwargs), "ml", "a"), "qa", "b")
    if target == "coef":
        coef = kwargs["bundle_root"] / "multimodal" / "classifier" / "coef.npy"
        arr = np.load(coef)
        arr[0, 0] += 1.0
        np.save(coef, arr)
    elif target == "code":
        (root / "ml" / "pinned.py").write_text("VALUE = 3\n")
    elif target == "config":
        kwargs["config_path"].write_text(kwargs["config_path"].read_text() + "# edit\n")
    else:
        with kwargs[target].open("ab") as file:
            file.write(b"\n")
    with pytest.raises(FreezeError, match=message):
        verify(record, bundle_root=kwargs["bundle_root"], root=root,
               manifest=kwargs["manifest"], split=kwargs["split"])


def test_unsigned_verification_requires_handover_files(frozen_inputs):
    root, kwargs = frozen_inputs
    record = collect(**kwargs)
    kwargs["manifest"].unlink()
    with pytest.raises(FreezeError, match="cannot read Train/Validation manifest"):
        verify(record, bundle_root=kwargs["bundle_root"], root=root, manifest=kwargs["manifest"],
               split=kwargs["split"], require_signed=False)


def test_cli_refuses_to_overwrite_signed_record(frozen_inputs, tmp_path):
    root, kwargs = frozen_inputs
    out = tmp_path / "model-freeze.json"
    out.write_text(json.dumps(sign(collect(**kwargs), "ml", "a")))
    code = main(["collect", "--bundle-root", str(kwargs["bundle_root"]), "--manifest", str(kwargs["manifest"]),
                 "--split", str(kwargs["split"]), "--out", str(out), "--replace"])
    assert code == 1
    assert json.loads(out.read_text())["signoffs"]["ml"]["by"] == "a"


def test_collect_refuses_test_ids(frozen_inputs, ml_fixture):
    _, kwargs = frozen_inputs
    kwargs["split"] = ml_fixture["unlocked_split"]
    with pytest.raises(PermissionError):
        collect(**kwargs)
