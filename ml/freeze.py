"""AFN-049: freeze record collector, sign-off and verification before Test.

The freeze record (``release/model-freeze.json``, schema ``afn-model-freeze-v1``)
pins everything the single Test run (#50) is allowed to use:

* data: SHA-256 of the Train/Validation manifest and the ID-withheld split CSV,
  their row counts and the number of locked Test rows;
* protocol: SHA-256 and ``status`` of ``configs/experiment.yaml``;
* selection: SHA-256 of ``configs/selected-models.json`` (#34);
* artifacts: per configuration the bundle ``metadata.json`` SHA-256, the
  checksum of every array file, model ID/version, C and threshold (#35);
* code: SHA-256 of every file that changes features, scores or the Test
  command, plus the git commit and whether those files were uncommitted.

``collect`` cross-checks those sources and refuses inconsistent inputs. Soft
gaps (protocol still ``proposed``, uncommitted code, fixture bundles, no Test
command yet) become ``blockers``. ``sign`` refuses while blockers remain, and
signs the canonical record hash, so any later edit voids both signatures.
``verify`` (used by #50) requires ML and QA signatures and recomputes every
hash from disk.

The collector never reads Test: it loads the Train/Validation handover only.

    .venv/bin/python -m ml.freeze collect --bundle-root backend/artifacts \\
        --manifest data/private/ml-v2/train-validation/manifest.jsonl \\
        --split data/private/ml-v2/train-validation/split.csv --out release/model-freeze.json
    .venv/bin/python -m ml.freeze sign --record release/model-freeze.json --role ml --by <github-login>
    .venv/bin/python -m ml.freeze verify --record release/model-freeze.json --bundle-root backend/artifacts
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.model_bundle import BUNDLE_DIRS, load_bundle
from ml import REPO_ROOT
from ml.common import DEFAULT_EXPERIMENT_CONFIG, load_dataset, load_experiment_config, sha256_file

SCHEMA = "afn-model-freeze-v1"
ROLES = ("ml", "qa")
LOCKED_PROTOCOL_STATUS = "locked"
DEFAULT_SELECTED = REPO_ROOT / "configs" / "selected-models.json"
DEFAULT_RECORD = REPO_ROOT / "release" / "model-freeze.json"
EVALUATION_MODULE = "ml/evaluate_test.py"
EVALUATION_COMMAND = ("python -m ml.evaluate_test --freeze release/model-freeze.json "
                      "--bundle-root backend/artifacts --locked-split <train-validation/split.csv> "
                      "--manifest <qa-only/manifest-test.jsonl> --split <qa-only/split.csv> "
                      "--image-root data --offline --out-dir reports")

# Files whose content decides features, scores, labels or the Test command.
CODE_FILES = (
    "backend/app/model_bundle.py",
    "backend/app/preprocessing.py",
    "configs/clip-reference.json",
    "configs/experiment.yaml",
    "ml/__init__.py",
    "ml/common.py",
    "ml/evaluate_test.py",
    "ml/export_artifacts.py",
    "ml/extract_embeddings.py",
    "ml/freeze.py",
    "ml/train_image.py",
    "ml/train_multimodal.py",
    "ml/train_text.py",
)


class FreezeError(RuntimeError):
    """Inputs disagree, the record was edited after signing, or it is not signed."""


# ----------------------------------------------------------------- helpers


def canonical_sha256(record: dict[str, Any]) -> str:
    """Hash of everything except the signature block and the derived status."""
    body = {k: v for k, v in record.items() if k not in ("status", "signoffs")}
    data = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _rel(path: Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).name


def code_snapshot(root: Path = REPO_ROOT, files: tuple[str, ...] = CODE_FILES) -> dict[str, Any]:
    """SHA-256 of each pinned file (``None`` when absent) plus git commit/dirty state."""
    hashes = {rel: (sha256_file(root / rel) if (root / rel).is_file() else None) for rel in files}
    commit, dirty = None, None
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                capture_output=True, text=True).stdout.strip() or None
        status = subprocess.run(["git", "status", "--porcelain", "--", *files], cwd=root, check=True,
                                capture_output=True, text=True).stdout
        dirty = bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"git_commit": commit, "uncommitted_changes": dirty, "files_sha256": hashes}


def _bundle_entry(bundle_root: Path, name: str, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle_dir = bundle_root / BUNDLE_DIRS[name]
    bundle = load_bundle(bundle_dir, expected_configuration=name)  # checksums verified here
    meta = bundle.metadata
    entry = {
        "bundle_dir": _rel(bundle_dir, root),
        "model_id": bundle.model_id,
        "model_version": bundle.model_version,
        "bundle_status": meta["status"],
        "is_fixture": bool(meta["is_fixture"]),
        "C": float(meta["classifier"]["C"]),
        "threshold": float(meta["threshold"]),
        "feature_dim": int(meta["feature_dim"]),
        "validation_macro_f1": meta["selection"]["validation_macro_f1"],
        "metadata_sha256": sha256_file(bundle_dir / "metadata.json"),
        "files_sha256": {rel: info["sha256"] for rel, info in sorted(meta["files"].items())},
        "encoder": meta["image"]["encoder"] if meta["image"] else None,
    }
    return entry, meta


# ----------------------------------------------------------------- collect


def collect(*, bundle_root: Path, manifest: Path, split: Path,
            selected_path: Path = DEFAULT_SELECTED, config_path: Path = DEFAULT_EXPERIMENT_CONFIG,
            root: Path = REPO_ROOT, code_files: tuple[str, ...] = CODE_FILES,
            created_at: str | None = None, allow_fixture: bool = False) -> dict[str, Any]:
    """Build a draft record; raise ``FreezeError`` when the pinned sources disagree.

    ``allow_fixture`` exists for tests and smoke runs; the record still says
    ``FIXTURE_SMOKE_NOT_RESEARCH`` and #50 then labels its output the same way.
    """
    cfg = load_experiment_config(config_path)
    selected = json.loads(Path(selected_path).read_text(encoding="utf-8"))
    dataset = load_dataset(manifest, split)  # Train/Validation only; Test IDs stay withheld
    config_sha = sha256_file(config_path)

    problems: list[str] = []
    inputs = selected.get("inputs", {})
    expected_inputs = {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
                       "experiment_config_sha256": config_sha}
    for key, value in expected_inputs.items():
        if inputs.get(key) != value:
            problems.append(f"selected-models {key} does not match the file on disk")
    if selected.get("test_split", {}).get("loaded") is not False:
        problems.append("selected-models does not record test_split.loaded = false")
    if selected.get("selection_split") != "validation":
        problems.append("selection was not made on Validation")

    configurations: dict[str, Any] = {}
    label_maps = set()
    for name in BUNDLE_DIRS:
        chosen = selected.get("configurations", {}).get(name)
        if chosen is None:
            problems.append(f"{name}: missing from selected-models")
            continue
        entry, meta = _bundle_entry(Path(bundle_root), name, root)
        training = meta["training"]
        for key, value in expected_inputs.items():
            if training.get(key) != value:
                problems.append(f"{name}: bundle {key} differs from the selection inputs")
        if (entry["C"], entry["threshold"]) != (float(chosen["C"]), float(chosen["threshold"])):
            problems.append(f"{name}: bundle C/threshold differ from selected-models")
        if meta["classifier"]["fit_split"] != "train" or meta["test_predictions_included"]:
            problems.append(f"{name}: bundle was not fit on Train only")
        if training.get("n_train") != len(dataset.rows("train")):
            problems.append(f"{name}: bundle n_train differs from the manifest")
        if meta["preprocess_version"] != cfg["preprocessing"]["version"]:
            problems.append(f"{name}: preprocess_version differs from the protocol")
        label_maps.add(json.dumps(meta["label_map"], sort_keys=True))
        configurations[name] = entry
    if len(label_maps) > 1:
        problems.append("bundles disagree on the label map")
    if problems:
        raise FreezeError("; ".join(problems))

    code = code_snapshot(root, code_files)
    fixture = any(c["is_fixture"] for c in configurations.values())
    blockers = []
    if cfg.get("status") != LOCKED_PROTOCOL_STATUS:
        blockers.append(f"protocol status is '{cfg.get('status')}', expected '{LOCKED_PROTOCOL_STATUS}'")
    if code["uncommitted_changes"] is not False:
        blockers.append("pinned code files have uncommitted changes or git state is unknown")
    if code["files_sha256"].get(EVALUATION_MODULE) is None and EVALUATION_MODULE in code_files:
        blockers.append(f"final Test command ({EVALUATION_MODULE}) is not in the code snapshot")
    if fixture and not allow_fixture:
        blockers.append("fixture bundles are not research artifacts")

    return {
        "schema": SCHEMA,
        "status": "draft",
        "created_at": created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_kind": "FIXTURE_SMOKE_NOT_RESEARCH" if fixture else "VALIDATION_ONLY",
        "protocol": {"path": _rel(config_path, root), "sha256": config_sha, "status": cfg.get("status"),
                     "preprocess_version": cfg["preprocessing"]["version"], "seed": cfg["seed"],
                     "refit_on_train_and_validation": bool(cfg["refit_on_train_and_validation"])},
        "data": {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
                 "n_train": len(dataset.rows("train")), "n_validation": len(dataset.rows("validation")),
                 "test_locked_rows": dataset.locked_counts.get("test", 0), "split_unit": "group_id"},
        "selection": {"path": _rel(selected_path, root), "sha256": sha256_file(selected_path),
                      "run_id": selected.get("run_id"), "split": "validation", "metric": "macro_f1"},
        "label_map": json.loads(label_maps.pop()),
        "configurations": configurations,
        "code": code,
        "evaluation": {
            "module": EVALUATION_MODULE,
            "command": EVALUATION_COMMAND,
            "labels": ["fake", "real"],
            "positive_label": "fake",
            "threshold_comparison": "greater_than_or_equal",
            "metrics": ["macro_f1", "accuracy", "per_class_precision_recall_f1_support",
                        "confusion_matrix_rows_true_cols_pred", "delta_macro_f1_multimodal_minus_text"],
            "runs_allowed": 1,
            "rerun_policy": "technical failure only, with a recorded reason; never for tuning",
        },
        "blockers": blockers,
        "signoffs": {role: None for role in ROLES},
    }


# ------------------------------------------------------------- sign/verify


def _status(record: dict[str, Any]) -> str:
    return "signed" if all(record["signoffs"].get(r) for r in ROLES) else "draft"


def sign(record: dict[str, Any], role: str, by: str, *, note: str | None = None,
         at: str | None = None) -> dict[str, Any]:
    """Add one role's signature over the canonical record hash."""
    if role not in ROLES:
        raise FreezeError(f"role must be one of {ROLES}")
    if not by or not by.strip():
        raise FreezeError("signer is required")
    if record.get("schema") != SCHEMA:
        raise FreezeError("not a freeze record")
    if record["blockers"]:
        raise FreezeError("cannot sign while blockers remain: " + "; ".join(record["blockers"]))
    digest = canonical_sha256(record)
    for other, sig in record["signoffs"].items():
        if sig and sig["record_sha256"] != digest:
            raise FreezeError(f"{other} signed a different version of this record")
    record["signoffs"][role] = {"by": by.strip(), "at": at or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"), "record_sha256": digest, "note": note}
    record["status"] = _status(record)
    return record


def verify(record: dict[str, Any], *, bundle_root: Path, root: Path = REPO_ROOT,
           require_signed: bool = True) -> dict[str, Any]:
    """Recompute every pinned hash; raise ``FreezeError`` on any difference."""
    if record.get("schema") != SCHEMA:
        raise FreezeError("not a freeze record")
    digest = canonical_sha256(record)
    problems = []
    if require_signed:
        for role in ROLES:
            sig = record.get("signoffs", {}).get(role)
            if not sig:
                problems.append(f"missing {role} signature")
            elif sig.get("record_sha256") != digest:
                problems.append(f"{role} signature does not match the record (edited after signing)")
        if record.get("status") != "signed":
            problems.append("record status is not 'signed'")
        if record.get("blockers"):
            problems.append("record still lists blockers")
    protocol = record["protocol"]
    if sha256_file(root / protocol["path"]) != protocol["sha256"]:
        problems.append("experiment config changed since freeze")
    selection = record["selection"]
    if sha256_file(root / selection["path"]) != selection["sha256"]:
        problems.append("selected-models changed since freeze")
    files = record["code"]["files_sha256"]
    current = code_snapshot(root, tuple(files))["files_sha256"]
    changed = sorted(rel for rel in files if current.get(rel) != files[rel])
    if changed:
        problems.append("pinned code changed since freeze: " + ", ".join(changed))
    for name, entry in record["configurations"].items():
        bundle_dir = Path(bundle_root) / BUNDLE_DIRS[name]
        try:
            bundle = load_bundle(bundle_dir, expected_configuration=name,
                                 expected_metadata_sha256=entry["metadata_sha256"])
        except Exception as exc:  # noqa: BLE001 - reported as a freeze mismatch
            problems.append(f"{name}: bundle does not match the frozen metadata ({type(exc).__name__})")
            continue
        files_now = {rel: info["sha256"] for rel, info in sorted(bundle.metadata["files"].items())}
        if files_now != entry["files_sha256"] or bundle.model_version != entry["model_version"]:
            problems.append(f"{name}: bundle arrays or version differ from the freeze")
    if problems:
        raise FreezeError("; ".join(problems))
    return record


def read_record(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_record(record: dict[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect", help="write a draft freeze record")
    c.add_argument("--bundle-root", type=Path, required=True)
    c.add_argument("--manifest", type=Path, required=True, help="Train/Validation manifest (no Test)")
    c.add_argument("--split", type=Path, required=True, help="split CSV with Test IDs withheld")
    c.add_argument("--selected", type=Path, default=DEFAULT_SELECTED)
    c.add_argument("--experiment-config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG)
    c.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    c.add_argument("--replace", action="store_true", help="overwrite an unsigned draft")
    s = sub.add_parser("sign", help="add the ML or QA signature")
    s.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    s.add_argument("--role", choices=ROLES, required=True)
    s.add_argument("--by", required=True, help="GitHub login of the person signing")
    s.add_argument("--note")
    v = sub.add_parser("verify", help="recompute every hash; exit 1 on mismatch")
    v.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    v.add_argument("--bundle-root", type=Path, required=True)
    v.add_argument("--allow-unsigned", action="store_true", help="check hashes of a draft")
    args = parser.parse_args(argv)

    try:
        if args.command == "collect":
            if args.out.exists():
                old = read_record(args.out)
                if any(old.get("signoffs", {}).values()):
                    raise FreezeError("refusing to overwrite a signed record")
                if not args.replace:
                    raise FreezeError(f"{args.out} exists; pass --replace to overwrite the draft")
            record = collect(bundle_root=args.bundle_root, manifest=args.manifest, split=args.split,
                             selected_path=args.selected, config_path=args.experiment_config)
            write_record(record, args.out)
            print(f"draft written: {_rel(args.out, REPO_ROOT)}  record_sha256={canonical_sha256(record)}")
            for blocker in record["blockers"]:
                print(f"BLOCKER: {blocker}")
            return 0 if not record["blockers"] else 2
        if args.command == "sign":
            record = sign(read_record(args.record), args.role, args.by, note=args.note)
            write_record(record, args.record)
            print(f"{args.role} signed; status={record['status']}")
            return 0
        verify(read_record(args.record), bundle_root=args.bundle_root, require_signed=not args.allow_unsigned)
        print("freeze record matches the files on disk")
        return 0
    except FreezeError as exc:
        print(f"FREEZE ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
