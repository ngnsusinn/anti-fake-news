"""Validate AFN-016 decisions against a checksummed, private recovery snapshot."""

import argparse
import hashlib
import io
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from PIL import Image

from ml import REPO_ROOT
from app.config import IMAGE_MAX_BYTES, IMAGE_MAX_PIXELS
from app.preprocessing import PreprocessingError, load_image_rgb, preprocess_text
from scripts.verify_recovery_snapshots import read_ids, sha256


SCHEMA = REPO_ROOT / "data" / "manifest.schema.json"
VERSION = "afn-manifest-validation-v1"


def validate_image(record, image_root):
    name = record["path"]
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError("image path must be relative to image root")
    path = (image_root / relative).resolve()
    if not path.is_relative_to(image_root):
        raise ValueError("image path escapes image root")
    try:
        with path.open("rb") as handle:
            data = handle.read(IMAGE_MAX_BYTES + 1)
        if len(data) > IMAGE_MAX_BYTES or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("image byte limit or checksum mismatch")
        with Image.open(io.BytesIO(data)) as image:
            if Image.MIME.get(image.format) != record["media_type"]:
                raise ValueError("image MIME type differs from manifest")
        load_image_rgb(data, max_pixels=IMAGE_MAX_PIXELS)
    except (OSError, Image.DecompressionBombError, PreprocessingError):
        raise ValueError("image is unreadable or exceeds API image limits") from None


def read_decisions(path, image_root):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    records = {}
    with path.open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except ValueError:
                raise ValueError(f"decisions line {number}: expected a JSON record") from None
            error = next(validator.iter_errors(row), None)
            if error:
                raise ValueError(f"decisions line {number}: manifest schema check failed ({error.validator})")
            sid = row["sample_id"]
            if sid in records or sid != f'{row["source"]}:{row["label"]}:{row["source_id"]}':
                raise ValueError(f"decisions line {number}: duplicate or inconsistent sample ID")
            if row["status"] == "accepted":
                try:
                    source = urlsplit(row["source_url"])
                except ValueError:
                    raise ValueError(f"decisions line {number}: invalid article URL") from None
                try:
                    if source.scheme not in {"http", "https"} or not source.hostname:
                        raise ValueError("missing web article URL")
                    if not row["publisher"].strip() or not row["rights"]["evidence"].strip():
                        raise ValueError("missing publisher or rights evidence")
                    preprocess_text(row["title"], row["body"])
                    validate_image(row["image"], image_root)
                except PreprocessingError:
                    raise ValueError(f"decisions line {number}: incompatible article text") from None
                except ValueError as error:
                    raise ValueError(f"decisions line {number}: {error}") from None
            records[sid] = row
    return records


def validate_batch(decisions, snapshot, snapshot_sha256, image_root, out):
    digest = sha256(snapshot)
    if digest != snapshot_sha256.lower():
        raise ValueError("recovery snapshot SHA-256 does not match handoff")
    inventory = read_ids(snapshot)
    rows = read_decisions(decisions, image_root.resolve(strict=True))
    if not inventory or set(rows) != inventory:
        raise ValueError(f"inventory mismatch: {len(inventory - rows.keys())} unaccounted, "
                         f"{len(rows.keys() - inventory)} unexpected")
    if len({row["is_fixture"] for row in rows.values()}) != 1:
        raise ValueError("fixture and production decisions must be validated separately")
    states = Counter(row["status"] for row in rows.values())
    exclusions = Counter(row["exclusion_reason"] for row in rows.values() if row["status"] == "rejected")
    by_source_label = Counter(f'{r["source"]}:{r["label"]}:{r["status"]}' for r in rows.values())
    if out.exists():
        raise FileExistsError("choose a new private output directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temporary:
        directory = Path(temporary) / "batch"
        directory.mkdir()
        manifest = directory / "manifest.jsonl"
        with manifest.open("w", encoding="utf-8", newline="\n") as handle:
            for sid in sorted(rows):
                handle.write(json.dumps(rows[sid], ensure_ascii=False, sort_keys=True) + "\n")
        report = {"version": VERSION, "fixture": next(iter(rows.values()))["is_fixture"],
                  "snapshot_sha256": digest, "manifest_sha256": sha256(manifest),
                  "inventory": len(inventory), "by_status": states, "excluded_by_reason": exclusions,
                  "by_source_label_status": by_source_label}
        (directory / "validation.json").write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        directory.rename(out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new directory in private storage")
    args = parser.parse_args()
    try:
        report = validate_batch(args.decisions, args.snapshot, args.snapshot_sha256, args.image_root, args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
