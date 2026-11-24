"""AFN-019: Text-only pipeline (shared preprocessing -> TF-IDF -> Logistic Regression).

The vectoriser vocabulary/IDF is fit on Train only (guarded); Validation is
only transformed. Run on a manifest + split (Train/Validation only):

    .venv/bin/python -m ml.train_text --manifest M.jsonl --split S.csv [--out result.json]

Scores on fixture data are smoke checks, never research results.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.preprocessing import PreprocessingError, preprocess_text
from ml.common import (
    Dataset,
    Sample,
    ids_of,
    labels_to_y,
    load_dataset,
    load_experiment_config,
    require_train,
    summarize_result,
    tune_on_validation,
)


@dataclass
class TextFeatures:
    vectorizer: Any
    X_train: Any  # scipy CSR, float64
    X_val: Any
    train_ids: list[str]
    val_ids: list[str]
    truncated_train: int
    truncated_val: int

    @property
    def dim(self) -> int:
        return int(self.X_train.shape[1])


def model_texts(samples: Sequence[Sample]) -> tuple[list[str], int]:
    """Shared preprocessing for every sample; returns texts and #truncated."""
    texts, truncated = [], 0
    for s in samples:
        try:
            result = preprocess_text(s.title, s.body)
        except PreprocessingError as exc:
            raise PreprocessingError(f"{s.sample_id}: {exc}") from exc
        texts.append(result.text)
        truncated += int(result.truncated)
    return texts, truncated


def make_vectorizer(cfg: dict[str, Any]):
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    tf = cfg["text_features"]
    return TfidfVectorizer(
        ngram_range=tuple(tf["ngram_range"]),
        max_features=tf["max_features"],
        min_df=tf["min_df"],
        sublinear_tf=tf["sublinear_tf"],
        norm=tf["norm"],
        lowercase=tf["lowercase"],
        dtype=np.float64,
    )


def fit_text_vectorizer(train: Sequence[Sample], cfg: dict[str, Any]):
    require_train(train, "TF-IDF vectoriser")
    texts, _ = model_texts(train)
    return make_vectorizer(cfg).fit(texts)


def build_text_features(train: Sequence[Sample], val: Sequence[Sample],
                        cfg: dict[str, Any]) -> TextFeatures:
    vectorizer = fit_text_vectorizer(train, cfg)
    train_texts, trunc_train = model_texts(train)
    val_texts, trunc_val = model_texts(val)
    return TextFeatures(
        vectorizer=vectorizer,
        X_train=vectorizer.transform(train_texts).tocsr(),
        X_val=vectorizer.transform(val_texts).tocsr(),
        train_ids=ids_of(train),
        val_ids=ids_of(val),
        truncated_train=trunc_train,
        truncated_val=trunc_val,
    )


def run_text_only(dataset: Dataset, cfg: dict[str, Any],
                  features: TextFeatures | None = None) -> dict[str, Any]:
    train, val = dataset.rows("train"), dataset.rows("validation")
    feats = features or build_text_features(train, val, cfg)
    positive = cfg["selection"]["positive_label"]
    tune = tune_on_validation(feats.X_train, labels_to_y(train, positive),
                              feats.X_val, labels_to_y(val, positive), cfg)
    result = summarize_result("text-only", tune, feature_dim=feats.dim,
                              train_ids=feats.train_ids, val_ids=feats.val_ids,
                              is_fixture=dataset.is_fixture)
    result["text"] = {"vocabulary_size": len(feats.vectorizer.vocabulary_),
                      "truncated_train": feats.truncated_train,
                      "truncated_validation": feats.truncated_val}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    cfg = load_experiment_config(args.config)
    dataset = load_dataset(args.manifest, args.split)
    result = run_text_only(dataset, cfg)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
