"""AFN-035 bundle export/load tests (synthetic fixture; FakeImageEncoder is a test double)."""

import io
import json
import shutil

import numpy as np
import pytest

from app.model_bundle import (
    BUNDLE_DIRS,
    BundleError,
    check_encoder_identity,
    load_bundle,
    load_label_map,
    sha256_bytes,
)
from ml.common import load_dataset
from ml.export_artifacts import export_all
from ml.train_text import build_text_features


@pytest.fixture
def dataset(ml_fixture):
    return load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])


@pytest.fixture
def exported(dataset, ml_config, fake_encoder, tmp_path):
    out = tmp_path / "artifacts"
    inputs = {"manifest_sha256": dataset.manifest_sha256, "split_sha256": dataset.split_sha256,
              "experiment_config_sha256": "0" * 64}
    report = export_all(dataset, ml_config, fake_encoder, out, inputs=inputs)
    return out, report


def _rewrite_meta(bundle_dir, mutate):
    path = bundle_dir / "metadata.json"
    meta = json.loads(path.read_text())
    mutate(meta)
    path.write_text(json.dumps(meta))


# -------------------------------------------------------------------- export


def test_three_bundles_label_map_and_report(exported):
    out, report = exported
    assert set(report["bundles"]) == {"text-only", "image-only", "multimodal"}
    for name, info in report["bundles"].items():
        assert (out / BUNDLE_DIRS[name] / "metadata.json").is_file()
        assert info["parity"]["labels_equal"] is True
        assert info["parity"]["max_abs_score_diff"] <= info["parity"]["atol"]
    assert load_label_map(out)["classes"] == {"0": "real", "1": "fake"}


def test_metadata_marks_candidate_fixture_without_test_data(exported, dataset):
    out, _ = exported
    for name, folder in BUNDLE_DIRS.items():
        meta = json.loads((out / folder / "metadata.json").read_text())
        assert meta["status"] == "candidate"  # until #49 freeze
        assert meta["is_fixture"] is True and meta["evidence_kind"] == "FIXTURE_SMOKE_NOT_RESEARCH"
        assert meta["model_id"].endswith("-fixture") and meta["model_version"].endswith("-fixture")
        assert meta["test_predictions_included"] is False
        assert meta["training"]["n_train"] == len(dataset.rows("train"))
        assert meta["training"]["manifest_sha256"] == dataset.manifest_sha256
        assert meta["classifier"]["fit_split"] == "train"
        if meta["image"] is not None:
            assert meta["image"]["packaged"] is False  # reference only, weights not bundled
    dumped = "".join(p.read_text(errors="ignore") for p in out.rglob("*.json"))
    assert '"test"' not in dumped.replace('"test_predictions_included"', "")


def test_export_refuses_test_rows(ml_fixture, ml_config, fake_encoder, tmp_path):
    unlocked = load_dataset(ml_fixture["unlocked_manifest"], ml_fixture["unlocked_split"],
                            splits=("train", "validation", "test"), allow_test=True)
    with pytest.raises(PermissionError):
        export_all(unlocked, ml_config, fake_encoder, tmp_path / "x", inputs={})


def test_feature_dims_and_fusion_order(exported, fake_encoder):
    out, report = exported
    text_dim = report["bundles"]["text-only"]["feature_dim"]
    assert report["bundles"]["image-only"]["feature_dim"] == fake_encoder.dim
    assert report["bundles"]["multimodal"]["feature_dim"] == text_dim + fake_encoder.dim
    meta = json.loads((out / "multimodal" / "metadata.json").read_text())
    assert meta["fusion"] == {"order": ["text", "image"], "dtype": "float64"}


# --------------------------------------------------------- offline == online


def test_text_features_match_sklearn_on_unseen_text(exported, dataset, ml_config):
    out, _ = exported
    feats = build_text_features(dataset.rows("train"), dataset.rows("validation"), ml_config)
    bundle = load_bundle(out / "text_only")
    texts = ["Shocking SECRET cure https://x.test viral hoax", "senate budget " * 900, "zzz unseen words"]
    expected = feats.vectorizer.transform(texts).toarray()
    assert np.allclose(bundle.text_features(texts).toarray(), expected, atol=1e-12)


def test_predict_returns_contract_fields(exported, fake_encoder, dataset):
    out, _ = exported
    from app.preprocessing import load_image_rgb

    sample = dataset.rows("validation")[0]
    emb = fake_encoder.encode([load_image_rgb(sample.image_path.read_bytes())])
    for folder in BUNDLE_DIRS.values():
        bundle = load_bundle(out / folder)
        pred = bundle.predict(sample.title, sample.body, emb if bundle.uses_image else None)
        assert pred.label in ("fake", "real")
        assert 0.0 <= pred.fake_score <= 1.0 and np.isfinite(pred.fake_score)
        assert pred.label == ("fake" if pred.fake_score >= bundle.threshold else "real")
        assert isinstance(pred.text_truncated, bool)
        assert pred.model_id == bundle.model_id and pred.model_version == bundle.model_version


def test_long_body_sets_text_truncated(exported):
    out, _ = exported
    pred = load_bundle(out / "text_only").predict("t", "word " * 2000)
    assert pred.text_truncated is True


def test_missing_modality_rejected(exported):
    out, _ = exported
    with pytest.raises(ValueError):
        load_bundle(out / "multimodal").predict("t", "body text here", None)


# ---------------------------------------------------------------- validation


def test_tampered_array_rejected(exported):
    out, _ = exported
    coef = out / "multimodal" / "classifier" / "coef.npy"
    arr = np.load(coef)
    arr[0, 0] += 1.0
    np.save(coef, arr)
    with pytest.raises(BundleError, match="checksum|size"):
        load_bundle(out / "multimodal")


def test_pickled_array_rejected_even_with_matching_checksum(exported):
    out, _ = exported
    bundle = out / "text_only"
    buf = io.BytesIO()
    np.save(buf, np.array([{"evil": 1}], dtype=object), allow_pickle=True)
    data = buf.getvalue()
    (bundle / "classifier" / "intercept.npy").write_bytes(data)
    _rewrite_meta(bundle, lambda m: m["files"].update(
        {"classifier/intercept.npy": {"sha256": sha256_bytes(data), "bytes": len(data)}}))
    with pytest.raises(BundleError):
        load_bundle(bundle)


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(threshold=1.5),
    lambda m: m.update(threshold=True),
    lambda m: m.update(preprocess_version="afn-preprocess-v0"),
    lambda m: m.update(schema_version="other"),
    lambda m: m.update(label_map={"0": "fake", "1": "fake"}),
    lambda m: m.update(test_predictions_included=True),
    lambda m: m.update(status="released"),
    lambda m: m.update(model_version=" "),
    lambda m: m.update(feature_dim=m["feature_dim"] + 1),
    lambda m: m["fusion"].update(order=["image", "text"]),
    lambda m: m["image"].update(packaged=True),
    lambda m: m["files"].pop("text/idf.npy"),
], ids=["thr>1", "thr-bool", "preprocess", "schema", "label_map", "test-preds", "status",
        "empty-version", "dim", "fusion-order", "packaged", "file-list"])
def test_bad_metadata_rejected(exported, mutate):
    out, _ = exported
    _rewrite_meta(out / "multimodal", mutate)
    with pytest.raises(BundleError):
        load_bundle(out / "multimodal")


def test_missing_file_and_wrong_configuration_rejected(exported):
    out, _ = exported
    with pytest.raises(BundleError):
        load_bundle(out / "text_only", expected_configuration="multimodal")
    (out / "text_only" / "text" / "idf.npy").unlink()
    with pytest.raises(BundleError):
        load_bundle(out / "text_only")
    with pytest.raises(BundleError):
        load_bundle(out / "does-not-exist")


def test_error_message_never_contains_paths(exported, tmp_path):
    out, _ = exported
    shutil.rmtree(out / "image_only" / "classifier")
    with pytest.raises(BundleError) as info:
        load_bundle(out / "image_only")
    assert str(tmp_path) not in str(info.value)


def test_encoder_identity_must_match(exported, fake_encoder_factory):
    out, _ = exported
    bundle = load_bundle(out / "multimodal")
    good = fake_encoder_factory()
    check_encoder_identity(bundle, good.identity, good.dim)
    with pytest.raises(BundleError, match="revision"):
        check_encoder_identity(bundle, fake_encoder_factory(revision="other").identity, good.dim)
    with pytest.raises(BundleError, match="dimension"):
        check_encoder_identity(bundle, good.identity, good.dim + 1)
    check_encoder_identity(load_bundle(out / "text_only"), {}, 0)  # text-only needs no encoder
