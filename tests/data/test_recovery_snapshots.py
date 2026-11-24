import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_recovery_snapshots import SNAPSHOT_COUNTS, sha256, verify_snapshots


class RecoverySnapshotsTest(unittest.TestCase):
    def test_checksums_counts_and_nested_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            snapshots = [directory / f"snapshot-{count}.jsonl" for count in SNAPSHOT_COUNTS]
            for snapshot, count in zip(snapshots, SNAPSHOT_COUNTS, strict=True):
                snapshot.write_text(
                    "".join(json.dumps({"sample_id": f"fixture-{i}"}) + "\n" for i in range(count)),
                    encoding="utf-8",
                )
            final = directory / "valid-400.jsonl"
            final.write_bytes(snapshots[-1].read_bytes())
            sums = directory / "SHA256SUMS"

            def write_checksums():
                sums.write_text(
                    "".join(f"{sha256(path)}  {path.name}\n" for path in snapshots),
                    encoding="utf-8",
                )

            write_checksums()
            final_digest = sha256(final)
            self.assertEqual(
                verify_snapshots(sums, final, snapshots, expected_final_sha256=final_digest.upper()),
                final_digest,
            )
            with self.assertRaisesRegex(ValueError, "independently recorded"):
                verify_snapshots(sums, final, snapshots, expected_final_sha256="0" * 64)

            changed = snapshots[1].read_text(encoding="utf-8").replace('"fixture-0"', '"fixture-new"')
            snapshots[1].write_text(changed, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_snapshots(sums, final, snapshots)
            write_checksums()
            with self.assertRaisesRegex(ValueError, "missing IDs"):
                verify_snapshots(sums, final, snapshots)


if __name__ == "__main__":
    unittest.main()
