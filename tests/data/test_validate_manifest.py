import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.validate_manifest import validate_batch


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_batch_validates_inventory_and_shared_image_rules(tmp_path):
    sample_path = Path(__file__).parent / "fixtures" / "manifest-v1.jsonl"
    accepted = next(row for row in map(json.loads, sample_path.read_text(encoding="utf-8").splitlines())
                    if row["status"] == "accepted")
    image = tmp_path / "synthetic.png"
    Image.new("RGB", (16, 16)).save(image)
    accepted["image"] = {"path": image.name, "media_type": "image/png",
                         "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
    rejected = dict(accepted, source_id="excluded", status="rejected", image=None,
                    exclusion_reason="missing_image")
    rejected["sample_id"] = f'{rejected["source"]}:{rejected["label"]}:excluded'
    snapshot = tmp_path / "snapshot.jsonl"
    write_rows(snapshot, [{"sample_id": row["sample_id"]} for row in [accepted, rejected]])
    snapshot_hash = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    decisions = tmp_path / "decisions.jsonl"
    out = tmp_path / "out"
    write_rows(decisions, [accepted])
    with pytest.raises(ValueError, match="1 unaccounted"):
        validate_batch(decisions, snapshot, snapshot_hash, tmp_path, out)
    accepted["image"]["media_type"] = "image/jpeg"
    write_rows(decisions, [accepted, rejected])
    with pytest.raises(ValueError, match="MIME type"):
        validate_batch(decisions, snapshot, snapshot_hash, tmp_path, out)
    accepted["image"]["media_type"] = "image/png"
    write_rows(decisions, [accepted, rejected])
    report = validate_batch(decisions, snapshot, snapshot_hash, tmp_path, out)
    assert report["by_status"] == {"accepted": 1, "rejected": 1}
    assert report["excluded_by_reason"] == {"missing_image": 1}
    assert report["manifest_sha256"] == hashlib.sha256((out / "manifest.jsonl").read_bytes()).hexdigest()
