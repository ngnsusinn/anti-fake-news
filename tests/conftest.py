"""Shared fixtures for root-level tests (ML pipelines use synthetic data only)."""

import numpy as np
import pytest

import ml  # noqa: F401  (puts backend/ on sys.path so `app.preprocessing` imports)


class FakeImageEncoder:
    """TEST DOUBLE, not CLIP: deterministic features from pixel statistics.

    Used only to test ordering/caching/fusion logic quickly; never evidence of
    real image features. Real CLIP is covered by the opt-in AFN_CLIP_TESTS test.
    """

    dim = 8

    def __init__(self, revision="fake-rev-1"):
        self.identity = {"repo_id": "test-double/fake-encoder", "revision": revision,
                         "processor_config_sha256": "0" * 64,
                         "preprocess_version": "afn-preprocess-v1", "dtype": "float32"}
        self.calls = 0
        self.images_encoded = 0

    def encode(self, images):
        self.calls += 1
        self.images_encoded += len(images)
        rows = []
        for img in images:
            arr = np.asarray(img, dtype=np.float64) / 255.0
            mean, std = arr.mean(axis=(0, 1)), arr.std(axis=(0, 1))
            rows.append(np.concatenate([mean, std, [arr.shape[0] / 100.0, 1.0]]))
        return np.array(rows)


@pytest.fixture
def ml_fixture(tmp_path):
    from ml.fixtures import write_synthetic_dataset

    return write_synthetic_dataset(tmp_path / "fixture")


@pytest.fixture
def ml_config():
    from ml.common import load_experiment_config

    return load_experiment_config()


@pytest.fixture
def fake_encoder_factory():
    return FakeImageEncoder


@pytest.fixture
def fake_encoder(fake_encoder_factory):
    return fake_encoder_factory()
