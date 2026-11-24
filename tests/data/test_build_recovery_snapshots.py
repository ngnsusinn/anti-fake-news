import json
from zipfile import ZipFile

import pytest

from scripts.build_recovery_snapshots import build_snapshots
from scripts.verify_recovery_snapshots import read_ids, sha256


def test_build_preserves_original_bytes_and_uses_batch_order(tmp_path):
    ids = [f"synthetic-{i:03d}" for i in range(400)]
    final = tmp_path / "original.jsonl"
    final.write_bytes(
        ("\r\n".join(json.dumps({"sample_id": sid}) for sid in ids)).encode("utf-8")
    )
    order = tmp_path / "completion-order.txt"
    order.write_text("\n".join(reversed(ids)), encoding="utf-8")
    out = tmp_path / "package"
    with pytest.raises(ValueError, match="SHA-256"):
        build_snapshots(final, "0" * 64, order, out)
    assert not out.exists()
    digest = sha256(final)
    assert build_snapshots(final, digest, order, out) == digest
    assert (out / "valid-400.jsonl").read_bytes() == final.read_bytes()
    assert (out / "snapshot-400.jsonl").read_bytes() == final.read_bytes()
    assert read_ids(out / "snapshot-228.jsonl") == set(ids[-228:])
    with ZipFile(out / "validator-snapshots.zip") as package:
        assert package.testzip() is None
        assert package.read("SHA256SUMS") == (out / "SHA256SUMS").read_bytes()
    with pytest.raises(FileExistsError):
        build_snapshots(final, digest, order, out)
    order.write_text("\n".join([*ids[:-1], ids[0]]), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly once"):
        build_snapshots(final, digest, order, tmp_path / "bad-order")
