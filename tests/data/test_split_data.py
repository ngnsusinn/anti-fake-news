import csv
import json

import pytest

from ml.common import load_dataset
from ml.fixtures import write_synthetic_dataset
from scripts.group_samples import write_grouping
from scripts.split_data import write_split
from scripts.validate_manifest import validate_batch
from scripts.verify_recovery_snapshots import sha256


def test_batch_to_group_split_has_reproducible_locked_ml_handoff(tmp_path):
    source = write_synthetic_dataset(tmp_path / "input", counts={"train": 6, "validation": 2, "test": 2})
    rows = [json.loads(line) for line in source["unlocked_manifest"].read_text(encoding="utf-8").splitlines()]
    for i, row in enumerate(rows):
        row.update(publisher=f"Publisher {i}", title=None, body=f"topic{i} distinct{i}", group_id=None)
    decisions = tmp_path / "decisions.jsonl"
    decisions.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    snapshot = tmp_path / "snapshot.jsonl"
    snapshot.write_text("".join(json.dumps({"sample_id": row["sample_id"]}) + "\n" for row in rows),
                        encoding="utf-8")
    batch = tmp_path / "batch"
    img_root = source["image_root"]
    evidence = validate_batch(decisions, snapshot, sha256(snapshot), img_root, batch)
    mapping_dir = tmp_path / "groups"
    manifest = batch / "manifest.jsonl"
    _, _, approved_hash = write_grouping(manifest, evidence["manifest_sha256"], img_root, mapping_dir)
    groups = mapping_dir / "groups.json"
    audit = mapping_dir / "grouping-audit.json"
    first, second = tmp_path / "release-a", tmp_path / "release-b"
    with pytest.raises(ValueError, match="groups SHA-256"):
        write_split(manifest, groups, "0" * 64, audit, img_root, first)
    assert not first.exists()
    report = write_split(manifest, groups, approved_hash, audit, img_root, first)
    assert report == write_split(manifest, groups, approved_hash, audit, img_root, second)
    with pytest.raises(FileExistsError):
        write_split(manifest, groups, approved_hash, audit, img_root, first)

    ml, qa = first / "train-validation", first / "qa-only"
    data = load_dataset(ml / "manifest.jsonl", ml / "split.csv", ml / "images")
    test = load_dataset(qa / "manifest.jsonl", qa / "split.csv", qa / "images",
                        splits=("test",), allow_test=True)
    assert {s.label for s in data.rows("train")} == {"fake", "real"}
    assert data.locked_counts == {"test": len(test.rows("test"))}
    assert all(s.image_path.is_file() for s in data.rows("train") + data.rows("validation"))
    assert all(s.image_path.is_file() and not (ml / "images" / s.image_path.relative_to(qa / "images")).exists()
               for s in test.rows("test"))
    with (ml / "split.csv").open(encoding="utf-8", newline="") as handle:
        assert all(not row["sample_id"] for row in csv.DictReader(handle) if row["split"] == "test")
    sets = [json.loads((qa / (name + ".json")).read_bytes()) for name in ("train", "validation", "test")]
    group_ids = [{row["group_id"] for row in records} for records in sets]
    assert sum(map(len, sets)) == len(rows)
    assert sum(map(len, group_ids)) == len(set.union(*group_ids))
