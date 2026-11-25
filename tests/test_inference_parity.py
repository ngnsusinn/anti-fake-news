"""AFN-036 offline-vs-online parity harness (synthetic fixture; FakeImageEncoder is a test double).

Positive tests: the harness reference predictor matches the offline scikit-learn
path on Validation and on request edge cases. Mutant tests: deliberately broken
predictors (EXIF ignored, label_map ignored, wrong fusion order, no truncation,
stale model identity, crash, invalid output) must each be reported as FAIL.
"""

import io
import json
import os

import numpy as np
import pytest
from scipy import sparse

from app.model_bundle import BUNDLE_DIRS, BundleError, load_bundle
from app.preprocessing import l2_normalize_embeddings, load_image_rgb, preprocess_text
from app.schemas import PredictionResult
from ml.common import TestSplitLockedError, load_dataset
from ml.export_artifacts import export_all
from ml.inference_parity import (
    DEFAULT_SCORE_ATOL,
    OfflineReference,
    ParityError,
    ParitySample,
    ReferenceBundlePredictor,
    request_for,
    run_parity,
    samples_from_dataset,
)

CONFIGS = list(BUNDLE_DIRS)


@pytest.fixture
def dataset(ml_fixture):
    return load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])


@pytest.fixture
def bundles(dataset, ml_config, fake_encoder, tmp_path):
    out = tmp_path / "artifacts"
    export_all(dataset, ml_config, fake_encoder, out,
               inputs={"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
                       "experiment_config_sha256": "0" * 64})
    return out


@pytest.fixture
def val_samples(dataset):
    return samples_from_dataset(dataset.rows("validation"))


def _load(bundles, name):
    return load_bundle(bundles / BUNDLE_DIRS[name], expected_configuration=name)


def _parity(bundle, predictor, samples, encoder):
    return run_parity(bundle, predictor, samples, encoder=encoder if bundle.uses_image else None)


def _image(mode="RGB", size=(64, 40), fmt="PNG", exif_orientation=None, transparency=False):
    from PIL import Image

    rng = np.random.default_rng(3)
    arr = rng.integers(0, 255, size=(size[1], size[0], 3)).astype("uint8")
    arr[: size[1] // 2] = [230, 30, 30]  # top half red -> rotation changes the statistics
    img = Image.fromarray(arr)
    if mode == "RGBA":
        img = img.convert("RGBA")
        img.putalpha(Image.fromarray(np.where(arr[..., 0] > 128, 0, 255).astype("uint8")))
    elif mode == "P":
        img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
    buf = io.BytesIO()
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        kwargs["exif"] = exif.tobytes()
    if transparency:
        kwargs["transparency"] = 0
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


EDGE_SAMPLES = [
    ParitySample("edge-exif-rotated-jpeg", "Senate budget vote", "The official report said today.",
                 _image(fmt="JPEG", exif_orientation=6)),
    ParitySample("edge-rgba-png", "Shocking secret", "Viral hoax claims a miracle cure.", _image("RGBA")),
    ParitySample("edge-palette-transparency", None, "court study agency vote", _image("P", transparency=True)),
    ParitySample("edge-long-body", "Long", "miracle cure " * 1200, _image()),  # 2400 words > 1500
    ParitySample("edge-whitespace-text", "  Padded title ", "\n\t secret  hoax​ exposed  \n", _image()),
]


# ----------------------------------------------------------------- PASS


@pytest.mark.parametrize("name", CONFIGS)
def test_reference_predictor_matches_offline_on_validation(bundles, val_samples, fake_encoder, name):
    bundle = _load(bundles, name)
    report = _parity(bundle, ReferenceBundlePredictor(bundle, fake_encoder if bundle.uses_image else None),
                     val_samples, fake_encoder)
    assert report.passed, report.failures
    assert report.n == len(val_samples) and report.n_errors == 0
    assert report.max_abs_score_diff <= DEFAULT_SCORE_ATOL
    assert report.labels_equal and report.truncated_equal and report.identity_equal
    assert report.evidence_kind == "FIXTURE_SMOKE_NOT_RESEARCH"


@pytest.mark.parametrize("name", CONFIGS)
def test_reference_predictor_matches_offline_on_request_edge_cases(bundles, fake_encoder, name):
    bundle = _load(bundles, name)
    report = _parity(bundle, ReferenceBundlePredictor(bundle, fake_encoder if bundle.uses_image else None),
                     EDGE_SAMPLES, fake_encoder)
    assert report.passed, report.failures


def test_offline_reference_is_independent_of_bundle_scoring(bundles, dataset, ml_config, fake_encoder,
                                                            val_samples):
    """Offline = scikit-learn objects; it must agree with ModelBundle.fake_scores."""
    from ml.train_text import model_texts

    bundle = _load(bundles, "multimodal")
    off_scores, _, _ = OfflineReference(bundle, fake_encoder).score(val_samples)
    texts, _ = model_texts(dataset.rows("validation"))
    emb = fake_encoder.encode([load_image_rgb(s.image_bytes) for s in val_samples])
    assert np.allclose(off_scores, bundle.fake_scores(bundle.features(texts, emb)), atol=1e-12)


def test_text_truncation_is_compared(bundles, fake_encoder):
    bundle = _load(bundles, "text-only")
    report = _parity(bundle, ReferenceBundlePredictor(bundle, None), EDGE_SAMPLES[3:4], fake_encoder)
    assert report.passed
    assert request_for(EDGE_SAMPLES[3]).text.startswith("miracle")
    assert preprocess_text("Long", EDGE_SAMPLES[3].body).truncated is True


def test_flipped_label_map_scores_the_fake_class(bundles, val_samples, fake_encoder):
    """classes_/label_map: with {"0": "fake"}, fake_score must be 1 - P(class 1)."""
    bundle_dir = bundles / "text_only"
    before = OfflineReference(load_bundle(bundle_dir), None).score(val_samples)[0]
    meta_path = bundle_dir / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["label_map"] = {"0": "fake", "1": "real"}
    meta_path.write_text(json.dumps(meta))
    flipped = load_bundle(bundle_dir)
    after = OfflineReference(flipped, None).score(val_samples)[0]
    assert np.allclose(after, 1.0 - before, atol=1e-12)
    assert run_parity(flipped, ReferenceBundlePredictor(flipped, None), val_samples, encoder=None).passed


def test_request_ids_are_deterministic_and_text_is_trimmed():
    a, b = request_for(EDGE_SAMPLES[4]), request_for(EDGE_SAMPLES[4])
    assert a.request_id == b.request_id
    assert a.text == EDGE_SAMPLES[4].body.strip()


# ------------------------------------------------------- mutants -> FAIL


class _Base:
    def __init__(self, bundle, encoder):
        self.bundle, self.encoder = bundle, encoder

    def _result(self, score, truncated, **override):
        fields = {"label": "fake" if score >= self.bundle.threshold else "real", "fake_score": float(score),
                  "model_version": self.bundle.model_version, "model_id": self.bundle.model_id,
                  "text_truncated": truncated}
        fields.update(override)
        return PredictionResult(**fields)


class NoExifPredictor(_Base):
    """Decodes with Pillow directly: ignores EXIF orientation and the white alpha background."""

    def predict(self, inputs):
        from PIL import Image

        img = Image.open(io.BytesIO(inputs.image_bytes)).convert("RGB")
        pred = self.bundle.predict(inputs.title, inputs.text, self.encoder.encode([img]))
        return self._result(pred.fake_score, pred.text_truncated)


class IgnoresLabelMapPredictor(_Base):
    """Always reports P(classes_[1]) as fake_score."""

    def predict(self, inputs):
        pre = preprocess_text(inputs.title, inputs.text)
        z = float((self.bundle.text_features([pre.text]) @ self.bundle._coef.T).ravel()[0]
                  + self.bundle._intercept[0])
        return self._result(1.0 / (1.0 + np.exp(-z)), pre.truncated)


class SwappedFusionPredictor(_Base):
    """hstack([image, text]) instead of the bundle's [text, image]."""

    def predict(self, inputs):
        pre = preprocess_text(inputs.title, inputs.text)
        emb = l2_normalize_embeddings(self.encoder.encode([load_image_rgb(inputs.image_bytes)]))
        X = sparse.hstack([sparse.csr_matrix(emb.astype(np.float64)), self.bundle.text_features([pre.text])],
                          format="csr")
        return self._result(float(self.bundle.fake_scores(X)[0]), pre.truncated)


class NoTruncationPredictor(_Base):
    def predict(self, inputs):
        pre = preprocess_text(inputs.title, inputs.text, max_words=10**9)
        score = float(self.bundle.fake_scores(self.bundle.features([pre.text], None))[0])
        return self._result(score, pre.truncated)


class StaleIdentityPredictor(ReferenceBundlePredictor):
    def predict(self, inputs):
        return super().predict(inputs).model_copy(update={"model_version": "text-only-old-version"})


class CrashingPredictor:
    def predict(self, inputs):
        raise RuntimeError("model file missing")


class InvalidOutputPredictor:
    def predict(self, inputs):
        return {"label": "fake", "fake_score": float("nan"), "model_version": "v", "model_id": "m",
                "text_truncated": False}


def test_mutant_ignoring_exif_and_alpha_fails(bundles, fake_encoder):
    bundle = _load(bundles, "image-only")
    report = _parity(bundle, NoExifPredictor(bundle, fake_encoder), EDGE_SAMPLES[:3], fake_encoder)
    assert not report.passed
    failed = {f["sample_id"] for f in report.failures}
    assert {"edge-exif-rotated-jpeg", "edge-rgba-png"} <= failed
    assert all("score" in f["problems"] for f in report.failures)


def test_mutant_ignoring_label_map_fails(bundles, val_samples):
    bundle_dir = bundles / "text_only"
    meta = json.loads((bundle_dir / "metadata.json").read_text())
    meta["label_map"] = {"0": "fake", "1": "real"}
    (bundle_dir / "metadata.json").write_text(json.dumps(meta))
    bundle = load_bundle(bundle_dir)
    report = run_parity(bundle, IgnoresLabelMapPredictor(bundle, None), val_samples, encoder=None)
    assert not report.passed and report.max_abs_score_diff > DEFAULT_SCORE_ATOL


def test_mutant_with_swapped_fusion_order_fails(bundles, val_samples, fake_encoder):
    bundle = _load(bundles, "multimodal")
    report = _parity(bundle, SwappedFusionPredictor(bundle, fake_encoder), val_samples, fake_encoder)
    assert not report.passed
    assert report.max_abs_score_diff > DEFAULT_SCORE_ATOL


def test_mutant_without_truncation_fails(bundles, fake_encoder):
    bundle = _load(bundles, "text-only")
    report = _parity(bundle, NoTruncationPredictor(bundle, None), EDGE_SAMPLES[3:4], fake_encoder)
    assert not report.passed and not report.truncated_equal
    assert "text_truncated" in report.failures[0]["problems"]


def test_stale_model_version_fails(bundles, val_samples):
    bundle = _load(bundles, "text-only")
    report = run_parity(bundle, StaleIdentityPredictor(bundle, None), val_samples, encoder=None)
    assert not report.passed and not report.identity_equal
    assert report.max_abs_score_diff <= DEFAULT_SCORE_ATOL  # same scores, still rejected


@pytest.mark.parametrize("predictor", [CrashingPredictor(), InvalidOutputPredictor()], ids=["crash", "nan"])
def test_failing_model_is_never_replaced_by_a_score(bundles, val_samples, predictor):
    bundle = _load(bundles, "text-only")
    report = run_parity(bundle, predictor, val_samples, encoder=None)
    assert not report.passed and report.n_errors == len(val_samples)
    assert report.max_abs_score_diff is None
    for failure in report.failures:
        assert failure["online_score"] is None and failure["online_label"] is None
        assert failure["problems"] == ["predictor_error"]
    assert "model file missing" not in json.dumps(report.to_dict())  # no exception text leaks


# ------------------------------------------------- refusals / mismatches


def test_harness_refuses_test_rows(ml_fixture):
    unlocked = load_dataset(ml_fixture["unlocked_manifest"], ml_fixture["unlocked_split"],
                            splits=("train", "validation", "test"), allow_test=True)
    with pytest.raises(TestSplitLockedError):
        samples_from_dataset(unlocked.rows("test"))


def test_empty_input_is_an_error(bundles):
    with pytest.raises(ParityError):
        run_parity(_load(bundles, "text-only"), CrashingPredictor(), [], encoder=None)


def test_encoder_version_mismatch_refused_before_scoring(bundles, fake_encoder_factory):
    bundle = _load(bundles, "multimodal")
    other = fake_encoder_factory(revision="other-rev")
    with pytest.raises(BundleError, match="revision"):
        ReferenceBundlePredictor(bundle, other)
    with pytest.raises(BundleError, match="revision"):
        OfflineReference(bundle, other)


def test_preprocess_version_mismatch_refused(bundles):
    path = bundles / "text_only" / "metadata.json"
    meta = json.loads(path.read_text())
    meta["preprocess_version"] = "afn-preprocess-v0"
    path.write_text(json.dumps(meta))
    with pytest.raises(BundleError, match="preprocess_version"):
        load_bundle(bundles / "text_only")


@pytest.mark.skipif(os.environ.get("AFN_CLIP_TESTS") != "1",
                    reason="set AFN_CLIP_TESTS=1 to run with the real cached CLIP weights")
def test_real_clip_parity_on_fixture(dataset, ml_config, tmp_path):
    from ml.extract_embeddings import ClipImageEncoder

    encoder = ClipImageEncoder(offline=True)
    out = tmp_path / "clip-bundles"
    export_all(dataset, ml_config, encoder, out, inputs={})
    samples = samples_from_dataset(dataset.rows("validation")) + EDGE_SAMPLES
    for name in ("image-only", "multimodal"):
        bundle = _load(out, name)
        report = _parity(bundle, ReferenceBundlePredictor(bundle, encoder), samples, encoder)
        assert report.passed, report.failures
