"""AFN-036: offline-vs-online inference parity harness.

Compares, sample by sample, two independent ways of scoring the same article:

* **offline** (training-side reference): ``preprocess_text`` -> scikit-learn
  ``TfidfVectorizer`` rebuilt from the bundle's vocabulary/IDF -> image bytes
  -> ``load_image_rgb`` -> encoder -> L2 -> ``scipy.sparse.hstack`` in the
  bundle's fusion order -> scikit-learn ``LogisticRegression.predict_proba``
  -> the column whose class maps to ``fake`` in ``label_map`` -> threshold.
  It does not call ``ModelBundle.features/fake_scores``.
* **online** (serving side): a request-shaped ``PredictorInput`` (UUID, title,
  text, encoded image bytes) -> any object implementing the Backend
  ``Predictor`` protocol -> ``PredictionResult``.

Tolerance: ``|online.fake_score - offline.fake_score| <= atol`` (default
``1e-6``) for every sample; labels, ``text_truncated``, ``model_id`` and
``model_version`` must be identical. A predictor exception or a result that
fails the ``PredictionResult`` schema is a FAIL. It is never replaced by a
placeholder score.

``ReferenceBundlePredictor`` is a HARNESS REFERENCE so the harness can run
before Backend #37 exists. It is not the #37 predictor. Pass the real one with
``--predictor module:factory`` (``factory(bundle_dir) -> Predictor``).

    # synthetic fixture + pinned CLIP (exports throw-away fixture bundles)
    .venv/bin/python -m ml.inference_parity --fixture --offline --out cache/parity/fixture.json

    # a candidate export (#35) on Validation, after #34; Test is refused
    .venv/bin/python -m ml.inference_parity --bundle-root DIR --manifest M.jsonl \
        --split S.csv --image-root IMG --offline --out reports/inference-parity.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from app.model_bundle import BUNDLE_DIRS, ModelBundle, check_encoder_identity, load_bundle
from app.predictor import Predictor, PredictorInput
from app.preprocessing import l2_normalize_embeddings, load_image_rgb, preprocess_text
from app.schemas import PredictionResult
from ml import REPO_ROOT
from ml.common import Sample, TestSplitLockedError
from ml.extract_embeddings import ImageEncoder

DEFAULT_SCORE_ATOL = 1e-6
REQUEST_NAMESPACE = uuid.UUID("5d0f3c2e-6a59-4c1e-9a43-0a1f0b36a036")  # deterministic request IDs


class ParityError(RuntimeError):
    """The harness itself cannot run, e.g. Test rows or a bundle that does not load."""


# ------------------------------------------------------------------ inputs


@dataclass(frozen=True)
class ParitySample:
    """One article as both sides see it: raw title/body and encoded image bytes."""

    sample_id: str
    title: str | None
    body: str
    image_bytes: bytes | None


def samples_from_dataset(rows: Iterable[Sample]) -> list[ParitySample]:
    """Validation/Train rows only; the harness never reads Test before #49."""
    out = []
    for row in rows:
        if row.split not in ("train", "validation"):
            raise TestSplitLockedError("parity must not use Test rows (locked until #49)")
        data = row.image_path.read_bytes() if row.image_path is not None else None
        out.append(ParitySample(row.sample_id, row.title, row.body, data))
    return out


def request_for(sample: ParitySample) -> PredictorInput:
    """The request the Backend builds after multipart validation (#22/#23)."""
    return PredictorInput(request_id=uuid.uuid5(REQUEST_NAMESPACE, sample.sample_id),
                          title=sample.title, text=sample.body, image_bytes=sample.image_bytes or b"")


# ---------------------------------------------------------------- offline


class OfflineReference:
    """Training-side scorer rebuilt as scikit-learn objects from a bundle's arrays."""

    def __init__(self, bundle: ModelBundle, encoder: ImageEncoder | None, *, batch_size: int = 16) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        meta = bundle.metadata
        self.bundle = bundle
        self.encoder = encoder
        self.batch_size = batch_size  # same batching as ml.extract_embeddings at training time
        self.threshold = float(meta["threshold"])
        self.vectorizer = None
        if bundle.uses_text:
            text = meta["text"]
            # Only the checksum-verified arrays are shared with the bundle; the
            # transform itself is scikit-learn's, not ModelBundle.text_features.
            self.vectorizer = TfidfVectorizer(
                vocabulary=dict(bundle._counter.vocabulary), ngram_range=tuple(text["ngram_range"]), lowercase=text["lowercase"],
                token_pattern=text["token_pattern"], sublinear_tf=text["sublinear_tf"],
                norm=text["norm"], dtype=np.float64)
            self.vectorizer.idf_ = bundle._idf
        if bundle.uses_image:
            if encoder is None:
                raise ParityError("bundle needs an image encoder")
            check_encoder_identity(bundle, encoder.identity, encoder.dim)
        model = LogisticRegression()
        model.classes_ = np.array(meta["classes"])
        model.coef_ = bundle._coef
        model.intercept_ = bundle._intercept
        model.n_features_in_ = int(meta["feature_dim"])
        self.model = model
        fake_classes = [c for c in meta["classes"] if meta["label_map"][str(c)] == "fake"]
        self.fake_column = int(np.flatnonzero(model.classes_ == fake_classes[0])[0])
        self.order = meta["fusion"]["order"] if meta["fusion"] else (["text"] if bundle.uses_text else ["image"])

    def score(self, samples: Sequence[ParitySample]) -> tuple[np.ndarray, list[str], list[bool]]:
        from scipy import sparse

        blocks: dict[str, Any] = {}
        truncated = [False] * len(samples)
        if self.vectorizer is not None:
            pre = [preprocess_text(s.title, s.body) for s in samples]
            truncated = [p.truncated for p in pre]
            blocks["text"] = self.vectorizer.transform([p.text for p in pre])
        if self.encoder is not None and self.bundle.uses_image:
            images = [load_image_rgb(s.image_bytes) for s in samples]
            raw = np.vstack([self.encoder.encode(images[i:i + self.batch_size])
                             for i in range(0, len(images), self.batch_size)])
            emb = l2_normalize_embeddings(raw, expected_dim=self.encoder.dim)
            blocks["image"] = sparse.csr_matrix(emb.astype(np.float64))
        X = sparse.hstack([blocks[name] for name in self.order], format="csr", dtype=np.float64)
        scores = self.model.predict_proba(X)[:, self.fake_column]
        labels = ["fake" if s >= self.threshold else "real" for s in scores]
        return scores, labels, truncated


# ----------------------------------------------------------------- online


class ReferenceBundlePredictor:
    """HARNESS REFERENCE implementing the ``Predictor`` protocol; NOT AFN-037.

    Shows the request path the Backend predictor is expected to follow, so the
    harness has something to call before #37 lands. Replace it with the real
    predictor via ``--predictor``.
    """

    def __init__(self, bundle: ModelBundle, encoder: ImageEncoder | None) -> None:
        if bundle.uses_image:
            if encoder is None:
                raise ParityError("bundle needs an image encoder")
            check_encoder_identity(bundle, encoder.identity, encoder.dim)
        self.bundle = bundle
        self.encoder = encoder

    def predict(self, inputs: PredictorInput) -> PredictionResult:
        emb = None
        if self.bundle.uses_image:
            emb = self.encoder.encode([load_image_rgb(inputs.image_bytes)])
        pred = self.bundle.predict(inputs.title, inputs.text, emb)
        return PredictionResult(label=pred.label, fake_score=pred.fake_score,
                                model_version=pred.model_version, model_id=pred.model_id,
                                text_truncated=pred.text_truncated)


# ----------------------------------------------------------------- report


@dataclass
class CaseResult:
    sample_id: str
    offline_score: float
    offline_label: str
    offline_truncated: bool
    online_score: float | None = None
    online_label: str | None = None
    online_truncated: bool | None = None
    abs_diff: float | None = None
    error: str | None = None
    problems: list[str] = field(default_factory=list)


@dataclass
class ParityReport:
    configuration: str
    model_id: str
    model_version: str
    is_fixture: bool
    evidence_kind: str
    n: int
    atol: float
    max_abs_score_diff: float | None
    labels_equal: bool
    truncated_equal: bool
    identity_equal: bool
    n_errors: int
    passed: bool
    failures: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_parity(bundle: ModelBundle, predictor: Predictor, samples: Sequence[ParitySample], *,
               encoder: ImageEncoder | None, atol: float = DEFAULT_SCORE_ATOL,
               batch_size: int = 16, evidence_kind: str | None = None) -> ParityReport:
    """Score every sample both ways and compare. Never raises on predictor errors:
    they are recorded as failures (no placeholder score is substituted)."""
    if not samples:
        raise ParityError("no samples to compare")
    offline = OfflineReference(bundle, encoder, batch_size=batch_size)
    off_scores, off_labels, off_trunc = offline.score(samples)
    cases: list[CaseResult] = []
    for sample, s, lab, tr in zip(samples, off_scores, off_labels, off_trunc, strict=True):
        case = CaseResult(sample.sample_id, float(s), lab, bool(tr))
        try:
            output = predictor.predict(request_for(sample))
            if isinstance(output, PredictionResult):
                # Revalidate fields because model_copy updates can bypass validation.
                output = dict(output)
            result = PredictionResult.model_validate(output)
        except Exception as exc:  # noqa: BLE001 - every failure is a parity failure
            case.error = type(exc).__name__
            case.problems.append("predictor_error")
            cases.append(case)
            continue
        case.online_score, case.online_label = result.fake_score, result.label
        case.online_truncated = result.text_truncated
        case.abs_diff = abs(result.fake_score - case.offline_score)
        if not case.abs_diff <= atol:
            case.problems.append("score")
        if result.label != case.offline_label:
            case.problems.append("label")
        if result.label != ("fake" if result.fake_score >= bundle.threshold else "real"):
            case.problems.append("label_vs_threshold")
        if result.text_truncated != case.offline_truncated:
            case.problems.append("text_truncated")
        if (result.model_id, result.model_version) != (bundle.model_id, bundle.model_version):
            case.problems.append("model_identity")
        cases.append(case)

    diffs = [c.abs_diff for c in cases if c.abs_diff is not None]
    failures = [asdict(c) for c in cases if c.problems]
    is_fixture = bool(bundle.metadata.get("is_fixture"))
    return ParityReport(
        configuration=bundle.configuration, model_id=bundle.model_id, model_version=bundle.model_version,
        is_fixture=is_fixture,
        evidence_kind=evidence_kind or ("FIXTURE_SMOKE_NOT_RESEARCH" if is_fixture else "VALIDATION_ONLY"),
        n=len(cases), atol=atol, max_abs_score_diff=max(diffs) if diffs else None,
        labels_equal=not any({"label", "predictor_error"} & set(c.problems) for c in cases),
        truncated_equal=not any({"text_truncated", "predictor_error"} & set(c.problems) for c in cases),
        identity_equal=not any({"model_identity", "predictor_error"} & set(c.problems) for c in cases),
        n_errors=sum(c.error is not None for c in cases), passed=not failures, failures=failures)


# -------------------------------------------------------------------- CLI


PredictorFactory = Callable[[Path, ModelBundle, "ImageEncoder | None"], Predictor]


def resolve_factory(spec: str | None) -> PredictorFactory:
    if spec is None:
        return lambda _dir, bundle, encoder: ReferenceBundlePredictor(bundle, encoder)
    module, _, attr = spec.partition(":")
    factory = getattr(importlib.import_module(module), attr)
    return lambda bundle_dir, _bundle, _encoder: factory(bundle_dir)


def _fixture_inputs(work: Path, cfg: dict[str, Any], encoder: ImageEncoder) -> tuple[Path, Any]:
    from ml.common import load_dataset
    from ml.export_artifacts import export_all
    from ml.fixtures import write_synthetic_dataset

    paths = write_synthetic_dataset(work / "data")
    dataset = load_dataset(paths["manifest"], paths["split"], paths["image_root"])
    inputs = {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
              "experiment_config_sha256": "fixture"}
    export_all(dataset, cfg, encoder, work / "bundles", inputs=inputs)
    return work / "bundles", dataset


def main(argv: list[str] | None = None) -> int:
    from tempfile import TemporaryDirectory

    from ml.common import load_dataset, load_experiment_config
    from ml.extract_embeddings import ClipImageEncoder

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--fixture", action="store_true", help="synthetic data + throw-away fixture bundles")
    src.add_argument("--bundle-root", type=Path, help="export directory with text_only/image_only/multimodal")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--split", type=Path)
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--configurations", nargs="+", default=list(BUNDLE_DIRS))
    parser.add_argument("--predictor", help="module:factory, factory(bundle_dir) -> Predictor (e.g. #37)")
    parser.add_argument("--atol", type=float, default=DEFAULT_SCORE_ATOL)
    parser.add_argument("--hf-cache-dir", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    cfg = load_experiment_config()
    encoder = ClipImageEncoder(REPO_ROOT / cfg["image_features"]["reference"],
                               cache_dir=args.hf_cache_dir, offline=args.offline)
    factory = resolve_factory(args.predictor)
    with TemporaryDirectory(prefix="afn-parity-") as tmp:
        if args.fixture:
            bundle_root, dataset = _fixture_inputs(Path(tmp), cfg, encoder)
        else:
            if args.manifest is None or args.split is None:
                parser.error("--manifest and --split are required with --bundle-root")
            bundle_root = args.bundle_root
            dataset = load_dataset(args.manifest, args.split, args.image_root)  # Train/Val only
        samples = samples_from_dataset(dataset.rows("validation"))
        reports = {}
        for name in args.configurations:
            bundle_dir = bundle_root / BUNDLE_DIRS[name]
            bundle = load_bundle(bundle_dir, expected_configuration=name)
            predictor = factory(bundle_dir, bundle, encoder if bundle.uses_image else None)
            reports[name] = run_parity(bundle, predictor, samples, atol=args.atol,
                                       batch_size=int(cfg["image_features"]["batch_size"]),
                                       encoder=encoder if bundle.uses_image else None).to_dict()

    summary = {"split": "validation", "n_samples": len(samples), "atol": args.atol,
               "predictor": args.predictor or "ml.inference_parity:ReferenceBundlePredictor (harness reference)",
               "encoder": dict(encoder.identity), "reports": reports,
               "passed": all(r["passed"] for r in reports.values())}
    text = json.dumps(summary, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    for name, r in reports.items():
        max_diff = r["max_abs_score_diff"]
        formatted_diff = "n/a" if max_diff is None else f"{max_diff:.2e}"
        print(f"{name:11s} n={r['n']} max|diff|={formatted_diff} labels_equal={r['labels_equal']} "
              f"truncated_equal={r['truncated_equal']} identity_equal={r['identity_equal']} "
              f"errors={r['n_errors']} -> {'PASS' if r['passed'] else 'FAIL'}  [{r['evidence_kind']}]")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
