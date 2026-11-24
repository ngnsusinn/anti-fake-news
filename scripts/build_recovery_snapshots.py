"""Rebuild the private AFN-003 package from the original manifest and batch order."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.verify_recovery_snapshots import SNAPSHOT_COUNTS, read_ids, sha256, verify_snapshots


def build_snapshots(final, expected_sha256, completion_order, out):
    if sha256(final) != expected_sha256.lower():
        raise ValueError("original manifest SHA-256 differs from the DATA handoff")
    ids = read_ids(final)
    original_bytes = final.read_bytes()
    order = completion_order.read_text(encoding="utf-8-sig").splitlines()
    if len(ids) != SNAPSHOT_COUNTS[-1] or len(order) != len(ids) or set(order) != ids:
        raise ValueError("completion order must list every original sample ID exactly once")
    rows = {}
    for line in original_bytes.removeprefix(b"\xef\xbb\xbf").splitlines():
        row = json.loads(line)
        rows[row["sample_id"]] = line + b"\n"
    if set(rows) != ids:
        raise ValueError("original manifest changed while reading")
    if out.exists():
        raise FileExistsError("choose a new private output directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as directory:
        stage = Path(directory) / "batch"
        stage.mkdir()
        final_copy = stage / "valid-400.jsonl"
        final_copy.write_bytes(original_bytes)
        snapshots = [stage / f"snapshot-{count}.jsonl" for count in SNAPSHOT_COUNTS]
        for count, path in zip(SNAPSHOT_COUNTS[:-1], snapshots[:-1], strict=True):
            path.write_bytes(b"".join(rows[sample_id] for sample_id in order[:count]))
        snapshots[-1].write_bytes(original_bytes)
        evidence = [final_copy, *snapshots]
        checksums = stage / "SHA256SUMS"
        checksums.write_text(
            "".join(f"{sha256(path)}  {path.name}\n" for path in evidence),
            encoding="ascii", newline="\n",
        )
        digest = verify_snapshots(checksums, final_copy, snapshots, expected_final_sha256=expected_sha256)
        with ZipFile(stage / "validator-snapshots.zip", "w", compression=ZIP_DEFLATED) as package:
            for path in [*evidence, checksums]:
                package.writestr(path.name, path.read_bytes())
        stage.rename(out)
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final", required=True, type=Path)
    parser.add_argument("--expected-final-sha256", required=True, help="independent digest from DATA")
    parser.add_argument("--completion-order", required=True, type=Path, help="original journal order, one ID per line")
    parser.add_argument("--out", required=True, type=Path, help="new private output directory")
    args = parser.parse_args()
    try:
        digest = build_snapshots(args.final, args.expected_final_sha256, args.completion_order, args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Verified original manifest and all four snapshots. SHA-256: {digest}")


if __name__ == "__main__":
    main()
