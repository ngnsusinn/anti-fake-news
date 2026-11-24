"""Create an AFN-018 group split and separate ML and QA handoffs."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from hashlib import sha256 as hash_bytes
from pathlib import Path
from random import Random
from re import fullmatch
from tempfile import TemporaryDirectory

from scripts.group_samples import VERSION as GROUPING_VERSION, exact_keys
from scripts.validate_manifest import read_decisions
from scripts.verify_recovery_snapshots import sha256
from app.config import IMAGE_MAX_BYTES


NAMES = ("train", "validation", "test")
RATIOS = (0.70, 0.15, 0.15)
LABELS = {"fake", "real"}
SEED = 42


def assign_groups(rows, mapping):
    groups = defaultdict(list)
    for sid in sorted(rows):
        groups[mapping[sid]].append(sid)
    if len(groups) < len(NAMES):
        raise ValueError("need at least three independent groups")
    totals = Counter((row["source"], row["label"]) for row in rows.values())
    units = [(members, Counter((rows[sid]["source"], rows[sid]["label"]) for sid in members))
             for _, members in sorted(groups.items())]

    def loss(counts, sizes):
        terms = []
        for i, ratio in enumerate(RATIOS):
            expected = len(rows) * ratio
            terms.append((sizes[i] - expected) ** 2 / max(1, expected))
            for category, total in sorted(totals.items()):
                expected = total * ratio
                terms.append((counts[i][category] - expected) ** 2 / max(1, expected))
        return sum(terms)

    rng = Random(SEED)
    best = None
    for _ in range(100):
        order = units.copy()
        rng.shuffle(order)
        order.sort(key=lambda unit: -len(unit[0]))
        sizes, counts, parts = [0] * 3, [Counter() for _ in NAMES], [[] for _ in NAMES]
        for ids, category_counts in order:
            choices = []
            for i in range(len(NAMES)):
                counts[i].update(category_counts)
                sizes[i] += len(ids)
                choices.append(loss(counts, sizes))
                counts[i].subtract(category_counts)
                sizes[i] -= len(ids)
            i = min(range(len(NAMES)), key=choices.__getitem__)
            counts[i].update(category_counts)
            sizes[i] += len(ids)
            parts[i].extend(ids)
        if all(parts) and {rows[sid]["label"] for sid in parts[0]} == LABELS:
            score = loss(counts, sizes)
            if best is None or score < best[0]:
                best = score, parts
    if best is None:
        raise ValueError("no split found with three nonempty sets and both labels in Train; groups preserved")
    return dict(zip(NAMES, map(sorted, best[1]), strict=True))


def read_grouping(path, approved_sha, audit_path, manifest_hash, rows, fixture):
    data = path.read_bytes()
    digest = hash_bytes(data).hexdigest()
    if digest != approved_sha.lower():
        raise ValueError("groups SHA-256 differs from the approved handoff")
    mapping = json.loads(data)
    if (not isinstance(mapping, dict) or set(mapping) != set(rows)
            or not all(isinstance(gid, str) and fullmatch(r"group_[0-9]{4,}", gid)
                       for gid in mapping.values())):
        raise ValueError("groups must map exactly all accepted IDs to label-free group IDs")
    audit = json.loads(audit_path.read_bytes())
    if (not isinstance(audit, dict) or audit.get("version") != GROUPING_VERSION
            or audit.get("groups_sha256") != digest or audit.get("manifest_sha256") != manifest_hash
            or audit.get("group_sizes") != dict(Counter(mapping.values())) or audit.get("fixture") is not fixture):
        raise ValueError("group audit does not match the manifest and mapping")
    keys = {}
    for sid in sorted(rows):
        for key in exact_keys(rows[sid]):
            if keys.setdefault(key, mapping[sid]) != mapping[sid]:
                raise ValueError(f"cross-group {key[0]} relation")
    edges = audit.get("edges")
    if not isinstance(edges, list):
        raise ValueError("group audit is missing relationship evidence")
    for edge in edges:
        if (not isinstance(edge, list) or len(edge) != 4
                or not all(isinstance(sid, str) and sid in mapping for sid in edge[:2])
                or mapping[edge[0]] != mapping[edge[1]]):
            raise ValueError("group audit contains an invalid cross-group relation")
    return mapping, digest


def write_json(path, payload):
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_handoff(directory, partitions, rows, mapping, image_root, *, locked):
    directory.mkdir()
    images_dir = directory / "images"
    with (directory / "split.csv").open("w", encoding="utf-8", newline="") as splits, \
            (directory / "manifest.jsonl").open("w", encoding="utf-8", newline="\n") as manifest:
        writer = csv.writer(splits, lineterminator="\n")
        writer.writerow(("sample_id", "split", "group_id"))
        for name, ids in partitions.items():
            for sid in ids:
                gid = mapping[sid]
                if locked and name == "test":
                    writer.writerow(("", name, gid))
                    continue
                writer.writerow((sid, name, gid))
                row = dict(rows[sid], group_id=gid)
                manifest.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                if locked or name == "test":
                    image = row["image"]
                    source = (image_root / image["path"]).resolve()
                    if not source.is_relative_to(image_root):
                        raise ValueError("image path escapes image root")
                    with source.open("rb") as handle:
                        content = handle.read(IMAGE_MAX_BYTES + 1)
                    if len(content) > IMAGE_MAX_BYTES or hash_bytes(content).hexdigest() != image["sha256"]:
                        raise ValueError("image changed since manifest validation")
                    target = images_dir / image["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)


def write_split(manifest, groups, groups_sha, audit, image_root, out, *, version="v1"):
    if not fullmatch(r"v[1-9][0-9]*", version):
        raise ValueError("dataset version must use v1, v2, and so on")
    if out.exists():
        raise FileExistsError("choose a new private release directory")
    image_root = image_root.resolve(strict=True)
    manifest_hash = sha256(manifest)
    decisions = read_decisions(manifest, image_root)
    if sha256(manifest) != manifest_hash:
        raise ValueError("manifest changed during validation")
    fixture_flags = {row["is_fixture"] for row in decisions.values()}
    if len(fixture_flags) != 1 or any(row["status"] == "pending" for row in decisions.values()):
        raise ValueError("split requires a settled manifest, with fixtures and research data in separate releases")
    rows = {sid: row for sid, row in decisions.items() if row["status"] == "accepted"}
    if not rows:
        raise ValueError("manifest has no accepted samples")
    fixture = fixture_flags.pop()
    mapping, groups_hash = read_grouping(groups, groups_sha, audit, manifest_hash, rows, fixture)
    partitions = assign_groups(rows, mapping)
    report = {"dataset_version": version, "seed": SEED, "is_fixture": fixture,
              "manifest_sha256": manifest_hash, "groups_sha256": groups_hash, "splits": {}}
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temporary:
        stage = Path(temporary) / "release"
        stage.mkdir()
        write_handoff(stage / "train-validation", partitions, rows, mapping, image_root, locked=True)
        qa = stage / "qa-only"
        write_handoff(qa, partitions, rows, mapping, image_root, locked=False)
        for name, target in zip(NAMES, RATIOS, strict=True):
            ids = partitions[name]
            counts = Counter(rows[sid]["label"] for sid in ids)
            report["splits"][name] = {
                "samples": len(ids), "groups": len({mapping[sid] for sid in ids}),
                "target_fraction": target, "actual_fraction": len(ids) / len(rows),
                "deviation_pp": round(100 * (len(ids) / len(rows) - target), 4),
                "missing_labels": sorted(LABELS - counts.keys()), "by_label": counts,
                "by_source_label": Counter(f'{rows[sid]["source"]}:{rows[sid]["label"]}' for sid in ids),
            }
            write_json(qa / (name + ".json"), [{"sample_id": sid, "group_id": mapping[sid]} for sid in ids])
        report["sha256"] = {file.relative_to(stage).as_posix(): sha256(file)
                            for file in sorted(stage.rglob("*")) if file.is_file()}
        write_json(qa / "split-summary.json", report)
        stage.rename(out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--groups", type=Path, required=True)
    parser.add_argument("--groups-sha256", required=True, help="mapping SHA-256 approved by QA")
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new directory controlled by QA")
    parser.add_argument("--version", default="v1")
    args = parser.parse_args()
    try:
        write_split(args.manifest, args.groups, args.groups_sha256, args.audit,
                    args.image_root, args.out, version=args.version)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Created {args.version}. Review counts, missing labels and checksums in qa-only/split-summary.json.")


if __name__ == "__main__":
    main()
