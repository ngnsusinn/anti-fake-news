"""Offline ML pipelines for AFN (#19 text-only, #20 image-only, #21 multimodal).

Shared preprocessing lives in ``backend/app/preprocessing.py`` so training and
inference cannot drift; this package makes it importable as ``app.preprocessing``.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = str(REPO_ROOT / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
