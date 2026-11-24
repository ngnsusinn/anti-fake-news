"""Build AFN-017 connected components from a validated private manifest."""

import argparse
import json
import unicodedata
from collections import Counter, defaultdict
from hashlib import sha256 as hash_bytes
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, urlencode, urlsplit

import numpy as np
from PIL import Image
from scipy.fft import dctn
from sklearn.feature_extraction.text import TfidfVectorizer

from scripts.validate_manifest import read_decisions
from scripts.verify_recovery_snapshots import sha256
from app.preprocessing import load_image_rgb


VERSION = "afn-group-v2"
RULES = {
    "title_candidate": 0.30, "title_text": 0.72,
    "text_support": 0.35, "text_near": 0.90, "phash_distance": 4, "title_weight": 0.70,
}


def normalize(value):
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


def article_key(source_url):
    parsed = urlsplit(source_url)
    host = (parsed.hostname or "").removeprefix("www.")
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    if port is not None and port != {"http": 80, "https": 443}.get(parsed.scheme):
        host = f"{host}:{port}"
    query = sorted((key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                   if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"})
    return host, parsed.path.rstrip("/") or "/", urlencode(query)


def exact_keys(row):
    body = normalize(row["body"])
    keys = {
        "publisher": normalize(row["publisher"]),
        "event_id": normalize(row["event_id"]),
        "url": article_key(row["source_url"]),
        "body_sha256": hash_bytes(body.encode("utf-8")).hexdigest(),
        "image_sha256": row["image"]["sha256"],
    }
    return [(kind, value) for kind, value in keys.items() if value]


def phash(image):
    image = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    spectrum = dctn(np.asarray(image, dtype=float))[:8, :8]
    bits = (spectrum > np.median(spectrum)).ravel()
    return int("".join("1" if bit else "0" for bit in bits), 2)


def similarities(values):
    try:
        features = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True,
                                  stop_words="english").fit_transform(values)
    except ValueError as error:
        if "empty vocabulary" not in str(error):
            raise
        return np.zeros((len(values), len(values)))
    return (features @ features.T).toarray()


class UnionFind:
    def __init__(self, ids):
        self.parents = {sample_id: sample_id for sample_id in ids}

    def root(self, sample_id):
        while self.parents[sample_id] != sample_id:
            self.parents[sample_id] = self.parents[self.parents[sample_id]]
            sample_id = self.parents[sample_id]
        return sample_id

    def union(self, left, right):
        left, right = self.root(left), self.root(right)
        if left != right:
            self.parents[max(left, right)] = min(left, right)


def group_samples(rows, image_hashes):
    ids = sorted(rows)
    components = UnionFind(ids)
    edges = []
    candidates = []
    seen = {}

    def connect(left, right, kind, value=None):
        components.union(left, right)
        edges.append([left, right, kind, value])

    for sid in ids:
        for key in exact_keys(rows[sid]):
            if key in seen:
                connect(seen[key], sid, key[0])
            else:
                seen[key] = sid

    titles = similarities([normalize(rows[sid]["title"]) for sid in ids])
    bodies = similarities([normalize(rows[sid]["body"]) for sid in ids])
    for i, j in combinations(range(len(ids)), 2):
        left, right = ids[i], ids[j]
        title, body = float(titles[i, j]), float(bodies[i, j])
        if body >= RULES["text_near"]:
            connect(left, right, "text_near", round(body, 6))
        if title >= RULES["title_candidate"]:
            weight = RULES["title_weight"]
            score = weight * title + (1 - weight) * body
            accepted = score >= RULES["title_text"] and body >= RULES["text_support"]
            candidates.append([left, right, round(title, 6), round(body, 6), accepted])
            if accepted:
                connect(left, right, "event_candidate", round(score, 6))
        distance = (image_hashes[left] ^ image_hashes[right]).bit_count()
        if distance <= RULES["phash_distance"]:
            connect(left, right, "image_near", distance)

    members = defaultdict(list)
    for sid in ids:
        members[components.root(sid)].append(sid)
    mapping = {
        sid: f"group_{index:04d}"
        for index, key in enumerate(sorted(members), start=1) for sid in members[key]
    }
    return mapping, edges, candidates


def write_grouping(manifest, expected_sha, image_root, out):
    digest = sha256(manifest)
    if digest != expected_sha.lower():
        raise ValueError("manifest SHA-256 differs from AFN-016 handoff")
    image_root = image_root.resolve(strict=True)
    decisions = read_decisions(manifest, image_root)
    if sha256(manifest) != digest or len({row["is_fixture"] for row in decisions.values()}) > 1:
        raise ValueError("manifest changed during validation or mixes fixture and research rows")
    rows = {sid: row for sid, row in decisions.items() if row["status"] == "accepted"}
    if not rows:
        raise ValueError("manifest has no accepted samples")
    hashes = {}
    for sid, row in rows.items():
        image = row["image"]
        data = (image_root / image["path"]).read_bytes()
        if hash_bytes(data).hexdigest() != image["sha256"]:
            raise ValueError("image changed since validation")
        hashes[sid] = phash(load_image_rgb(data))
    mapping, edges, candidates = group_samples(rows, hashes)
    sizes = Counter(mapping.values())
    audit = {
        "version": VERSION, "manifest_sha256": digest, "rules": RULES,
        "fixture": next(iter(rows.values()))["is_fixture"],
        "accepted": len(rows), "pending": sum(row["status"] == "pending" for row in decisions.values()),
        "missing_event": sum(not row["event_id"] for row in rows.values()),
        "missing_publisher": sum(not row["publisher"] for row in rows.values()),
        "group_sizes": sizes, "edge_counts": Counter(edge[2] for edge in edges),
        "edges": edges, "event_candidates": candidates,
    }
    if out.exists():
        raise FileExistsError("choose a new private grouping directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temporary:
        staged = Path(temporary) / "grouping"
        staged.mkdir()
        groups = staged / "groups.json"
        groups.write_text(json.dumps(mapping, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        audit["groups_sha256"] = sha256(groups)
        (staged / "grouping-audit.json").write_text(
            json.dumps(audit, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        staged.rename(out)
    return len(rows), len(sizes), audit["groups_sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new directory in private storage")
    args = parser.parse_args()
    try:
        samples, groups, digest = write_grouping(args.manifest, args.manifest_sha256, args.image_root, args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{samples} accepted samples in {groups} groups. Mapping SHA-256: {digest}")


if __name__ == "__main__":
    main()
