"""AFN-021 fusion and three-configuration runner tests (synthetic data only)."""

import numpy as np
import pytest
from scipy import sparse

from ml.common import DataContractError, SampleOrderError, load_dataset
from ml.run_experiments import ALL_CONFIGS, run_all
from ml.train_multimodal import fuse_features


def _blocks():
    text = sparse.csr_matrix(np.array([[1.0, 0.0, 2.0], [0.0, 3.0, 0.0]]))
    image = np.array([[0.6, 0.8], [1.0, 0.0]], dtype=np.float32)
    return text, image, ["a", "b"]


def test_hstack_is_text_then_image_csr_float64():
    text, image, ids = _blocks()
    fused = fuse_features(text, ids, image, ids)
    assert sparse.isspmatrix_csr(fused) or isinstance(fused, sparse.csr_array)
    assert fused.dtype == np.float64
    assert fused.shape == (2, 5)
    dense = fused.toarray()
    assert np.array_equal(dense[:, :3], text.toarray())
    assert np.allclose(dense[:, 3:], image)


def test_swapped_sample_order_raises():
    text, image, ids = _blocks()
    with pytest.raises(SampleOrderError):
        fuse_features(text, ids, image[::-1], list(reversed(ids)))


def test_mismatched_ids_or_row_counts_raise():
    text, image, ids = _blocks()
    with pytest.raises(SampleOrderError):
        fuse_features(text, ids, image, ["a", "c"])
    with pytest.raises(SampleOrderError):
        fuse_features(text, ids, image[:1], ["a"])
    with pytest.raises(SampleOrderError):
        fuse_features(text[:1], ids, image, ids)


def test_image_first_order_rejected():
    text, image, ids = _blocks()
    with pytest.raises(DataContractError):
        fuse_features(text, ids, image, ids, order=("image", "text"))


@pytest.fixture
def dataset(ml_fixture):
    return load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])


def test_three_configurations_end_to_end_same_split(dataset, ml_config, fake_encoder):
    results = run_all(dataset, ml_config, fake_encoder)
    assert set(results) == set(ALL_CONFIGS)
    orders = {(r["train_order_sha256"], r["validation_order_sha256"]) for r in results.values()}
    assert len(orders) == 1
    mm = results["multimodal"]
    assert mm["feature_dim"] == results["text-only"]["feature_dim"] + fake_encoder.dim
    assert mm["fusion"]["order"] == ["text", "image"]
    for r in results.values():
        assert r["evidence_kind"] == "FIXTURE_SMOKE_NOT_RESEARCH"
        assert r["n_train"] == 28 and r["n_validation"] == 8  # Test never included


def test_classifiers_are_fit_on_train_rows_only(dataset, ml_config, fake_encoder, monkeypatch):
    from sklearn.linear_model import LogisticRegression

    fitted_rows = []
    original_fit = LogisticRegression.fit

    def recording_fit(self, X, y, *args, **kwargs):
        fitted_rows.append(X.shape[0])
        return original_fit(self, X, y, *args, **kwargs)

    monkeypatch.setattr(LogisticRegression, "fit", recording_fit)
    run_all(dataset, ml_config, fake_encoder)
    n_train = len(dataset.rows("train"))
    n_c = len(ml_config["selection"]["c_candidates"])
    assert fitted_rows == [n_train] * (3 * n_c)  # never Validation, never Train+Val


def test_runner_refuses_test_rows(ml_fixture, ml_config, fake_encoder):
    unlocked = load_dataset(ml_fixture["unlocked_manifest"], ml_fixture["unlocked_split"],
                            splits=("train", "validation", "test"), allow_test=True)
    assert len(unlocked.rows("test")) == 6
    with pytest.raises(PermissionError):
        run_all(unlocked, ml_config, fake_encoder)


def test_cli_has_no_test_option():
    from ml import run_experiments

    source = open(run_experiments.__file__, encoding="utf-8").read()
    assert "allow_test" not in source
    assert "--test" not in source


def test_unknown_configuration_rejected(dataset, ml_config, fake_encoder):
    with pytest.raises(ValueError):
        run_all(dataset, ml_config, fake_encoder, configs=["text-only", "bogus"])
