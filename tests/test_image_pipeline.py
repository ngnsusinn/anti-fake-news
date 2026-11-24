"""AFN-020 embedding/cache/Image-only tests (synthetic data; fake encoder is a test double)."""

import json
import os

import numpy as np
import pytest

from app.preprocessing import NonFiniteEmbeddingError
from ml.common import DataContractError, load_dataset
from ml.extract_embeddings import EmbeddingCache, EmbeddingSet, cache_key, extract_embeddings
from ml.train_image import build_image_features, run_image_only


@pytest.fixture
def dataset(ml_fixture):
    return load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])


def test_cache_key_changes_with_image_checkpoint_processor_and_preprocessing(fake_encoder):
    base = fake_encoder.identity
    key = cache_key("a" * 64, base)
    assert cache_key("a" * 64, dict(base)) == key
    assert cache_key("b" * 64, base) != key
    for field in ("revision", "processor_config_sha256", "preprocess_version", "repo_id", "dtype"):
        assert cache_key("a" * 64, base | {field: "changed"}) != key


def test_embeddings_shape_norm_dtype_and_order(dataset, fake_encoder):
    train = dataset.rows("train")
    emb = extract_embeddings(train, fake_encoder, batch_size=5)
    assert emb.matrix.shape == (len(train), fake_encoder.dim)
    assert emb.matrix.dtype == np.float32
    assert np.allclose(np.linalg.norm(emb.matrix, axis=1), 1.0, atol=1e-6)
    assert emb.sample_ids == [s.sample_id for s in train]
    assert fake_encoder.calls == 6  # ceil(28 / 5) batches
    # Row i belongs to sample i: re-embedding one sample alone gives the same row.
    single = extract_embeddings([train[7]], fake_encoder)
    assert np.allclose(single.matrix[0], emb.matrix[7], atol=1e-6)


def test_cache_hit_skips_encoder_and_returns_same_vectors(dataset, tmp_path, fake_encoder_factory):
    rows = dataset.rows("train")
    first_enc, second_enc = fake_encoder_factory(), fake_encoder_factory()
    cache = EmbeddingCache(tmp_path / "emb", first_enc.dim)
    first = extract_embeddings(rows, first_enc, cache=cache)
    second = extract_embeddings(rows, second_enc, cache=cache)
    assert second_enc.images_encoded == 0 and second.stats["cache_hits"] == len(rows)
    assert np.array_equal(first.matrix, second.matrix)


def test_cache_not_reused_when_checkpoint_changes(dataset, tmp_path, fake_encoder_factory):
    rows = dataset.rows("validation")
    first = fake_encoder_factory(revision="r1")
    other = fake_encoder_factory(revision="r2")
    cache = EmbeddingCache(tmp_path / "emb", first.dim)
    extract_embeddings(rows, first, cache=cache)
    extract_embeddings(rows, other, cache=cache)
    assert other.images_encoded == len(rows)


def test_corrupted_cache_entry_is_recomputed(dataset, tmp_path, fake_encoder_factory):
    rows = dataset.rows("validation")[:1]
    enc = fake_encoder_factory()
    cache = EmbeddingCache(tmp_path / "emb", enc.dim)
    extract_embeddings(rows, enc, cache=cache)
    (entry,) = list((tmp_path / "emb").rglob("*.npy"))
    np.save(entry, np.full(enc.dim, np.nan, dtype=np.float32))  # poison it
    again = fake_encoder_factory()
    out = extract_embeddings(rows, again, cache=cache)
    assert again.images_encoded == 1
    assert np.all(np.isfinite(out.matrix))


def test_image_sha_mismatch_rejected(ml_fixture, fake_encoder):
    lines = ml_fixture["manifest"].read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["image"]["sha256"] = "f" * 64
    lines[0] = json.dumps(row)
    ml_fixture["manifest"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    ds = load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])
    bad = [s for s in ds.rows("train") + ds.rows("validation") if s.sample_id == row["sample_id"]]
    with pytest.raises(DataContractError, match="sha256"):
        extract_embeddings(bad, fake_encoder)


def test_undecodable_image_fails_with_sample_id(dataset, fake_encoder):
    sample = dataset.rows("train")[0]
    sample.image_path.write_bytes(b"not an image")
    from dataclasses import replace

    broken = replace(sample, image_sha256=None)
    with pytest.raises(DataContractError, match=sample.sample_id):
        extract_embeddings([broken], fake_encoder)


def test_bad_encoder_output_rejected(dataset, fake_encoder, monkeypatch):
    rows = dataset.rows("validation")
    encode = fake_encoder.encode

    def nonfinite_output(images):
        output = encode(images)
        output[0, 0] = np.nan
        return output

    monkeypatch.setattr(fake_encoder, "encode", nonfinite_output)
    with pytest.raises(NonFiniteEmbeddingError):
        extract_embeddings(rows, fake_encoder)
    monkeypatch.setattr(fake_encoder, "encode", lambda images: encode(images)[:, :-1])
    with pytest.raises(DataContractError, match="shape"):
        extract_embeddings(rows, fake_encoder)


def test_embedding_set_check_detects_order_change(dataset, fake_encoder):
    rows = dataset.rows("validation")
    emb = extract_embeddings(rows, fake_encoder)
    with pytest.raises(DataContractError, match="order"):
        emb.check(list(reversed(emb.sample_ids)))
    dup = EmbeddingSet(emb.sample_ids[:1] * 2, emb.matrix[:2], emb.identity)
    with pytest.raises(DataContractError):
        dup.check()


def test_save_writes_ids_matrix_and_metadata(dataset, fake_encoder, tmp_path):
    emb = extract_embeddings(dataset.rows("validation"), fake_encoder)
    emb.save(tmp_path / "e.npz")
    loaded = np.load(tmp_path / "e.npz", allow_pickle=False)
    assert list(loaded["sample_ids"]) == emb.sample_ids
    assert np.array_equal(loaded["embeddings"], emb.matrix)
    meta = json.loads((tmp_path / "e.json").read_text())
    assert meta["identity"]["revision"] == fake_encoder.identity["revision"]


def test_image_only_end_to_end_on_fixture(dataset, ml_config, fake_encoder):
    emb_train, emb_val = build_image_features(dataset, fake_encoder, ml_config)
    result = run_image_only(dataset, ml_config, emb_train, emb_val)
    assert result["evidence_kind"] == "FIXTURE_SMOKE_NOT_RESEARCH"
    assert result["feature_dim"] == fake_encoder.dim
    assert result["n_train"] == 28 and result["n_validation"] == 8


@pytest.mark.skipif(os.environ.get("AFN_CLIP_TESTS") != "1",
                    reason="set AFN_CLIP_TESTS=1 to run with the real cached CLIP weights")
def test_real_clip_embeddings_on_fixture(dataset, tmp_path):
    from ml.extract_embeddings import ClipImageEncoder

    encoder = ClipImageEncoder(offline=True)
    rows = dataset.rows("validation")
    emb = extract_embeddings(rows, encoder, cache=EmbeddingCache(tmp_path / "emb", encoder.dim))
    assert emb.matrix.shape == (len(rows), 512)  # dimension measured from the model
    assert encoder.identity["revision"] == "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
    emb.check([s.sample_id for s in rows])
