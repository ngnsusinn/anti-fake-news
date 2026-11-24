"""End-to-end smoke of an exported bundle, the way the Backend predictor will run it.

Request-shaped inputs (title, body, encoded image bytes) ->
    preprocess_text / load_image_rgb -> pinned CLIP -> bundle -> label + fake_score

Uses synthetic inputs only; prints timings measured after model load.

    .venv/bin/python scripts/smoke_bundle.py --bundle backend/artifacts/multimodal --offline
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import ml  # noqa: E402,F401  (adds backend/ to sys.path)
from app.model_bundle import check_encoder_identity, load_bundle  # noqa: E402
from app.preprocessing import load_image_rgb  # noqa: E402
from ml.extract_embeddings import ClipImageEncoder  # noqa: E402


def synthetic_png(colour: tuple[int, int, int]) -> bytes:
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(7)
    arr = np.clip(np.array(colour) + rng.integers(-40, 40, size=(120, 160, 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", type=Path, default=REPO_ROOT / "backend" / "artifacts" / "multimodal")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--repeat", type=int, default=20)
    args = parser.parse_args()

    t0 = time.perf_counter()
    bundle = load_bundle(args.bundle)
    encoder = ClipImageEncoder(offline=args.offline) if bundle.uses_image else None
    if encoder is not None:
        check_encoder_identity(bundle, encoder.identity, encoder.dim)
    load_s = time.perf_counter() - t0

    requests = [
        ("Shocking secret cure exposed", "Viral hoax claims a miracle cure was banned, people said today.",
         synthetic_png((200, 60, 60))),
        ("Senate passes budget", "The senate report says the official budget vote passed in court today.",
         synthetic_png((60, 90, 200))),
    ]

    def predict(title: str, body: str, image_bytes: bytes):
        emb = None
        if encoder is not None:
            emb = encoder.encode([load_image_rgb(image_bytes)])
        return bundle.predict(title, body, emb)

    outputs = [predict(*r).__dict__ for r in requests]  # warm-up + results
    times = []
    for _ in range(max(1, args.repeat)):
        t = time.perf_counter()
        predict(*requests[0])
        times.append((time.perf_counter() - t) * 1000)

    print(json.dumps({
        "bundle": {"configuration": bundle.configuration, "model_id": bundle.model_id,
                   "model_version": bundle.model_version, "status": bundle.metadata["status"],
                   "is_fixture": bundle.metadata["is_fixture"], "threshold": bundle.threshold},
        "load_seconds": round(load_s, 3),
        "predictions_on_synthetic_inputs": outputs,
        "request_ms_median": round(statistics.median(times), 1),
        "request_ms_max": round(max(times), 1),
        "note": "Synthetic inputs; fixture bundles are not research models.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
