"""Check private AFN-003 review artifacts without exporting article content."""

import argparse
import hashlib
import json
import re
from pathlib import Path


SNAPSHOT_COUNTS = (228, 300, 350, 400)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_checksums(path):
    checksums = {}
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if not match:
            raise ValueError(f"Invalid checksum entry at line {number}")
        digest, name = match.groups()
        filename = re.split(r"[/\\]", name)[-1]
        if filename in checksums:
            raise ValueError(f"Duplicate checksum filename at line {number}")
        checksums[filename] = digest.lower()
    return checksums


def read_ids(path):
    ids = set()
    with path.open(encoding="utf-8-sig") as file:
        for number, line in enumerate(file, 1):
            try:
                record = json.loads(line)
                sample_id = record["sample_id"]
            except (ValueError, KeyError, IndexError, TypeError):
                raise ValueError(f"{path.name}:{number}: expected a JSON object with sample_id") from None
            if not isinstance(sample_id, str) or not sample_id.strip() or sample_id in ids:
                raise ValueError(f"{path.name}:{number}: empty or duplicate sample_id")
            ids.add(sample_id)
    return ids


def verify_snapshots(checksums_path, final_path, snapshots, *, expected_final_sha256=None):
    checksums = read_checksums(checksums_path)
    previous = set()
    last_digest = None
    for path, expected in zip(snapshots, SNAPSHOT_COUNTS, strict=True):
        digest = sha256(path)
        if checksums.get(path.name) != digest:
            raise ValueError(f"{path.name}: missing or mismatched SHA-256")
        current = read_ids(path)
        if len(current) != expected:
            raise ValueError(f"{path.name}: expected {expected} unique IDs, found {len(current)}")
        if not previous.issubset(current):
            raise ValueError(f"{path.name}: missing IDs from the preceding snapshot")
        previous, last_digest = current, digest

    digest = sha256(final_path)
    if digest != last_digest:
        raise ValueError("Final manifest differs from the 400-row snapshot")
    if expected_final_sha256 is not None:
        if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_final_sha256):
            raise ValueError("Expected final SHA-256 must contain 64 hexadecimal characters")
        if digest != expected_final_sha256.lower():
            raise ValueError("Final manifest differs from the independently recorded SHA-256")
    if final_path.name in checksums and checksums[final_path.name] != digest:
        raise ValueError("Final manifest SHA-256 does not match SHA256SUMS")
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checksums", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument(
        "--expected-final-sha256",
        help="Final manifest SHA-256 recorded independently from the package",
    )
    parser.add_argument("snapshots", type=Path, nargs=4, help="Paths in order: 228, 300, 350, 400 rows")
    args = parser.parse_args()
    try:
        digest = verify_snapshots(
            args.checksums, args.final, args.snapshots, expected_final_sha256=args.expected_final_sha256
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Verified 228, 300, 350 and 400 unique, nested IDs. Final SHA-256: {digest}")


if __name__ == "__main__":
    main()
