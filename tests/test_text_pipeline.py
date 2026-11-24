"""AFN-019 Text-only pipeline tests on synthetic fixtures (not research results)."""

import csv
import json

import pytest

from ml.common import (
    DataContractError,
    FitOnNonTrainError,
    Sample,
    TestSplitLockedError,
    load_dataset,
    selection_key,
)
from ml.train_text import build_text_features, fit_text_vectorizer, run_text_only


def _sample(sid, split, body, label="fake", title=None):
    return Sample(sample_id=sid, label=label, split=split, title=title, body=body,
                  group_id=None, image_path=None, image_sha256=None, is_fixture=True)


# ----------------------------------------------------------- fit-Train guard


def test_vectorizer_refuses_validation_or_test_rows(ml_config):
    train = [_sample("a", "train", "alpha beta"), _sample("b", "train", "alpha gamma")]
    for split in ("validation", "test"):
        with pytest.raises(FitOnNonTrainError):
            fit_text_vectorizer(train + [_sample("c", split, "alpha delta")], ml_config)
    with pytest.raises(FitOnNonTrainError):
        fit_text_vectorizer([], ml_config)


def test_vocabulary_never_contains_validation_only_tokens(ml_config):
    train = [_sample(f"t{i}", "train", "common words here shared", label=lab)
             for i, lab in enumerate(["fake", "real", "fake", "real"])]
    val = [_sample(f"v{i}", "validation", "zzvalonly zzvalonly common", label=lab)
           for i, lab in enumerate(["fake", "real"])]
    feats = build_text_features(train, val, ml_config)
    vocab = feats.vectorizer.vocabulary_
    assert not any("zzvalonly" in term for term in vocab)
    assert "common" in vocab
    assert feats.X_val.shape == (2, feats.dim)  # transformed, not fit


def test_shared_preprocessing_and_truncation_are_used(ml_config):
    long_body = " ".join(["word"] * 1600)
    train = [_sample("a", "train", long_body + " https://x.test/a", title="Title one"),
             _sample("b", "train", "word other https://y.test", label="real")]
    val = [_sample("v", "validation", "word https://z.test", label="real")]
    feats = build_text_features(train, val, ml_config)
    assert feats.truncated_train == 1 and feats.truncated_val == 0
    assert not any("http" in term or "test" in term for term in feats.vectorizer.vocabulary_)


def test_tfidf_parameters_come_from_config(ml_config):
    vec = fit_text_vectorizer([_sample("a", "train", "xx yy zz xx yy"),
                               _sample("b", "train", "xx yy ww")], ml_config)
    assert "xx yy" in vec.vocabulary_  # bigram kept (df=2), unigram+bigram range
    tf = ml_config["text_features"]
    assert vec.ngram_range == tuple(tf["ngram_range"]) == (1, 2)
    assert vec.max_features == tf["max_features"] == 5000
    assert vec.min_df == tf["min_df"] == 2
    assert vec.sublinear_tf is True and vec.norm == "l2"


def test_empty_body_after_normalisation_names_sample(ml_config):
    with pytest.raises(ValueError, match="only-url"):
        fit_text_vectorizer([_sample("only-url", "train", "https://example.test")], ml_config)


# ------------------------------------------------------ manifest/split inputs


def test_text_only_end_to_end_on_fixture(ml_fixture, ml_config):
    dataset = load_dataset(ml_fixture["manifest"], ml_fixture["split"], ml_fixture["image_root"])
    result = run_text_only(dataset, ml_config)
    assert result["evidence_kind"] == "FIXTURE_SMOKE_NOT_RESEARCH"
    assert result["n_train"] == 28 and result["n_validation"] == 8
    assert result["feature_dim"] == result["text"]["vocabulary_size"] > 0
    assert len(result["grid"]) == (len(ml_config["selection"]["c_candidates"])
                                   * len(ml_config["selection"]["threshold_candidates"]))
    assert result["selected"]["C"] in ml_config["selection"]["c_candidates"]
    json.dumps(result)  # serialisable run log


def test_test_split_is_locked(ml_fixture, monkeypatch):
    from pathlib import Path

    original_open = Path.open

    def guard_test_payload(path, *args, **kwargs):
        assert path != ml_fixture["unlocked_manifest"], "opened Test payload before freeze"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard_test_payload)
    with pytest.raises(TestSplitLockedError):
        load_dataset(ml_fixture["manifest"], ml_fixture["split"],
                     splits=("train", "validation", "test"))
    with pytest.raises(TestSplitLockedError, match="sample IDs"):
        load_dataset(ml_fixture["unlocked_manifest"], ml_fixture["unlocked_split"])
    dataset = load_dataset(ml_fixture["manifest"], ml_fixture["split"])
    assert "test" not in dataset.splits
    assert dataset.locked_counts == {"test": 6}
    with pytest.raises(TestSplitLockedError):
        dataset.rows("test")


def test_rows_sorted_by_sample_id(ml_fixture):
    dataset = load_dataset(ml_fixture["manifest"], ml_fixture["split"])
    for rows in dataset.splits.values():
        ids = [s.sample_id for s in rows]
        assert ids == sorted(ids)


def _rewrite_split(path, mutate):
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    rows = mutate(rows)
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)


def test_split_referencing_unknown_id_rejected(ml_fixture):
    _rewrite_split(ml_fixture["split"], lambda r: r + [["politifact:fake:nope", "train", "unused"]])
    with pytest.raises(DataContractError, match="missing manifest ids"):
        load_dataset(ml_fixture["manifest"], ml_fixture["split"])


def test_duplicate_split_id_rejected(ml_fixture):
    _rewrite_split(ml_fixture["split"], lambda r: r + [next(row for row in r[1:] if row[0])])
    with pytest.raises(DataContractError, match="duplicate sample_id"):
        load_dataset(ml_fixture["manifest"], ml_fixture["split"])


def test_test_group_overlapping_train_rejected_without_test_payload(ml_fixture):
    def share_train_group(rows):
        train_group = next(row[2] for row in rows[1:] if row[1] == "train")
        next(row for row in rows[1:] if row[1] == "test")[2] = train_group
        return rows

    _rewrite_split(ml_fixture["split"], share_train_group)
    with pytest.raises(DataContractError, match="spans several splits"):
        load_dataset(ml_fixture["manifest"], ml_fixture["split"])


def test_missing_group_in_split_rejected(ml_fixture):
    def remove_group(rows):
        rows[1][2] = " "
        return rows

    _rewrite_split(ml_fixture["split"], remove_group)
    with pytest.raises(DataContractError, match="group_id is required"):
        load_dataset(ml_fixture["manifest"], ml_fixture["split"])


@pytest.mark.parametrize("group_id", [None, "", "mismatched"])
def test_missing_or_mismatched_manifest_group_rejected(ml_fixture, group_id):
    lines = ml_fixture["manifest"].read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    rows[0]["group_id"] = group_id
    rows[0]["is_fixture"] = False
    ml_fixture["manifest"].write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                      encoding="utf-8")
    with pytest.raises(DataContractError, match="missing or mismatched manifest group_id"):
        load_dataset(ml_fixture["manifest"], ml_fixture["split"])


def test_premature_full_manifest_rejected(ml_fixture):
    with pytest.raises(DataContractError, match="no visible split assignment"):
        load_dataset(ml_fixture["unlocked_manifest"], ml_fixture["split"])


# ----------------------------------------------------------------- selection


def test_selection_tie_break_order():
    d = 12
    best = min([(0.8, 1.0, 0.4), (0.8, 1.0, 0.5), (0.8, 0.1, 0.6), (0.7, 0.01, 0.5)],
               key=lambda g: selection_key(g[0], g[1], g[2], d))
    assert best == (0.8, 1.0, 0.5)  # threshold closest to 0.5 wins ties
    best = min([(0.8, 10.0, 0.5), (0.8, 0.1, 0.5)], key=lambda g: selection_key(*g, d))
    assert best == (0.8, 0.1, 0.5)  # then lower C
    best = min([(0.8, 1.0, 0.6), (0.8, 1.0, 0.4)], key=lambda g: selection_key(*g, d))
    assert best == (0.8, 1.0, 0.4)  # then lower threshold
    best = min([(0.8 + 1e-14, 1.0, 0.3), (0.8, 1.0, 0.5)], key=lambda g: selection_key(*g, d))
    assert best == (0.8, 1.0, 0.5)  # scores compared after rounding to 12 decimals
