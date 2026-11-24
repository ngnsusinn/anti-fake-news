"""AFN-006 smoke test for the pinned, frozen CLIP ViT-B/32 image encoder.

Uses only synthetic images generated in memory (no research data, no external
image assets). Verifies: pinned checkpoint/processor, eval + frozen weights,
measured embedding dimension, finiteness, L2 norm, determinism, batch/single
parity, local cache (offline reload) and CPU timings.

Usage (from repository root):
    .venv/bin/python scripts/smoke_clip.py                 # download if needed
    .venv/bin/python scripts/smoke_clip.py --offline       # cache-only reload
    .venv/bin/python scripts/smoke_clip.py --report out.json

Exit code 0 only if every check passes. Timings are machine-specific
measurements for planning, not model-quality evidence.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app import preprocessing as pp  # noqa: E402  (shared AFN-005 module)

DEFAULT_CONFIG = REPO_ROOT / "configs" / "clip-reference.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="Hugging Face cache dir (default: $HF_HOME/hub or <repo>/cache/huggingface/hub)")
    parser.add_argument("--offline", action="store_true", help="Load from local cache only; never touch the network")
    parser.add_argument("--repeat", type=int, default=20, help="Timed single-image forward passes")
    parser.add_argument("--threads", type=int, default=None, help="torch.set_num_threads (default: torch default)")
    parser.add_argument("--report", type=Path, default=None, help="Also write the JSON report here")
    return parser.parse_args()


def resolve_cache_dir(arg: Path | None, config: dict) -> Path:
    if arg is not None:
        return arg.resolve()
    if os.environ.get(config["runtime"]["cache_env"]):
        return Path(os.environ[config["runtime"]["cache_env"]]) / "hub"
    return REPO_ROOT / config["runtime"]["default_cache_dir"] / "hub"


def machine_info() -> dict:
    import torch

    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count_logical": os.cpu_count(),
        "torch_threads": torch.get_num_threads(),
        "cuda_available": torch.cuda.is_available(),
        "mps_available": bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()),
    }
    try:
        if sys.platform == "darwin":
            import subprocess

            info["cpu_model"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                               capture_output=True, text=True, check=False).stdout.strip()
            mem = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False).stdout
            info["ram_gib"] = round(int(mem) / 2**30, 1)
        elif hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            info["ram_gib"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
        elif sys.platform == "win32":
            import ctypes

            class MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

            stat = MemStatus()
            stat.dwLength = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            info["ram_gib"] = round(stat.ullTotalPhys / 2**30, 1)
    except Exception:  # informational only
        pass
    return info


def synthetic_fixture_bytes() -> dict[str, bytes]:
    """Permitted fixtures: generated here, so no licensing or privacy concerns."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(42)
    out: dict[str, bytes] = {}

    def enc(img: Image.Image, fmt: str, **kw) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format=fmt, **kw)
        return buf.getvalue()

    grad = np.linspace(0, 255, 320, dtype=np.uint8)
    rgb = np.stack([np.tile(grad, (240, 1)), np.tile(grad[::-1], (240, 1)),
                    np.full((240, 320), 128, np.uint8)], axis=-1)
    out["gradient.jpg"] = enc(Image.fromarray(rgb), "JPEG", quality=92)
    noise = rng.integers(0, 256, size=(200, 300, 3), dtype=np.uint8)
    out["noise.png"] = enc(Image.fromarray(noise), "PNG")
    rgba = np.zeros((256, 256, 4), np.uint8)
    rgba[64:192, 64:192] = (200, 30, 30, 255)
    out["alpha.png"] = enc(Image.fromarray(rgba), "PNG")
    exif = Image.Exif()
    exif[0x0112] = 6
    out["exif_rotated.jpg"] = enc(Image.fromarray(rgb), "JPEG", quality=92, exif=exif)
    return out


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    enc_cfg, emb_cfg = config["encoder"], config["embedding"]
    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"

    import numpy as np
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from transformers import CLIPImageProcessor, CLIPModel

    transformers.logging.set_verbosity_error()
    if args.threads:
        torch.set_num_threads(args.threads)
    torch.manual_seed(0)

    checks: dict[str, bool] = {}
    timings: dict[str, float] = {}
    cache_dir = resolve_cache_dir(args.cache_dir, config)

    t0 = time.perf_counter()
    local_dir = snapshot_download(repo_id=enc_cfg["repo_id"], revision=enc_cfg["revision"],
                                  allow_patterns=enc_cfg["files"], cache_dir=str(cache_dir),
                                  local_files_only=args.offline)
    timings["fetch_or_locate_s"] = round(time.perf_counter() - t0, 3)
    checks["revision_dir_matches_pin"] = Path(local_dir).name == enc_cfg["revision"]
    checks["all_pinned_files_present"] = all((Path(local_dir) / f).is_file() for f in enc_cfg["files"])

    t0 = time.perf_counter()
    model = CLIPModel.from_pretrained(local_dir, dtype=torch.float32)
    processor = CLIPImageProcessor.from_pretrained(local_dir)
    model.eval()
    model.requires_grad_(False)
    timings["load_model_processor_s"] = round(time.perf_counter() - t0, 3)

    checks["eval_mode"] = not model.training
    checks["all_params_frozen"] = not any(p.requires_grad for p in model.parameters())
    checks["param_dtype_float32"] = all(p.dtype == torch.float32 for p in model.parameters())
    param_count = sum(p.numel() for p in model.parameters())
    weight_probe_before = model.visual_projection.weight.detach().clone()

    def encode(images) -> np.ndarray:
        inputs = processor(images=images, return_tensors="pt")
        with torch.inference_mode():
            out = model.get_image_features(pixel_values=inputs["pixel_values"])
        feats = out if isinstance(out, torch.Tensor) else out.pooler_output
        return feats.detach().cpu().numpy()

    fixtures = synthetic_fixture_bytes()
    images = [pp.load_image_rgb(data) for data in fixtures.values()]
    checks["exif_fixture_upright"] = images[3].size == (240, 320)

    t0 = time.perf_counter()
    raw_batch = encode(images)
    timings["first_batch_forward_s"] = round(time.perf_counter() - t0, 3)

    measured_dim = int(raw_batch.shape[-1])
    checks["dim_matches_model_config"] = measured_dim == int(model.config.projection_dim)
    checks["dim_matches_reference_config"] = measured_dim == int(emb_cfg["dim"])
    checks["raw_output_finite"] = bool(np.all(np.isfinite(raw_batch)))
    emb = pp.l2_normalize_embeddings(raw_batch, expected_dim=measured_dim)
    norms = np.linalg.norm(emb, axis=1)
    checks["l2_norm_is_one"] = bool(np.allclose(norms, 1.0, atol=1e-5))
    checks["embedding_dtype_float32"] = emb.dtype == np.float32
    checks["shape_rows_match_inputs"] = emb.shape == (len(images), measured_dim)

    again = pp.l2_normalize_embeddings(encode(images))
    checks["deterministic_repeat"] = bool(np.allclose(emb, again, atol=1e-6))
    singles = np.vstack([pp.l2_normalize_embeddings(encode([img])) for img in images])
    batch_single_diff = float(np.max(np.abs(singles - emb)))
    checks["batch_equals_single"] = batch_single_diff < 1e-4
    checks["distinct_images_distinct_embeddings"] = bool(np.max(np.abs(emb[0] - emb[1])) > 1e-3)
    checks["weights_unchanged"] = bool(torch.equal(weight_probe_before, model.visual_projection.weight))

    per_image = []
    single = [images[0]]
    for _ in range(max(1, args.repeat)):
        t0 = time.perf_counter()
        pp.l2_normalize_embeddings(encode(single))
        per_image.append((time.perf_counter() - t0) * 1000)
    timings["single_image_ms_median"] = round(statistics.median(per_image), 1)
    timings["single_image_ms_max"] = round(max(per_image), 1)
    timings["repeats"] = len(per_image)

    report = {
        "issue": "AFN-006",
        "synthetic_fixtures_only": True,
        "offline": args.offline,
        "encoder": {"repo_id": enc_cfg["repo_id"], "revision": enc_cfg["revision"],
                    "param_count": param_count, "image_size": int(model.config.vision_config.image_size)},
        "embedding": {"dim_measured": measured_dim, "dtype": str(emb.dtype),
                      "norm_min": float(norms.min()), "norm_max": float(norms.max()),
                      "batch_single_max_abs_diff": batch_single_diff},
        "versions": {"torch": torch.__version__, "transformers": transformers.__version__,
                     "numpy": np.__version__, "pillow": __import__("PIL").__version__,
                     "preprocess_version": pp.PREPROCESS_VERSION},
        "machine": machine_info(),
        "timings": timings,
        "checks": checks,
        "passed": all(checks.values()),
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
