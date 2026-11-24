"""AFN-021: Multimodal features = hstack([TF-IDF, CLIP]) -> Logistic Regression.

Fusion contract (configs/experiment.yaml ``fusion``):
- block order is text then image;
- rows are joined by sample_id and must be identical lists in identical order,
  otherwise ``SampleOrderError`` (no silent re-ordering or inner join);
- dense CLIP rows become CSR, both blocks use one dtype (float64).
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from ml.common import (
    Dataset,
    DataContractError,
    SampleOrderError,
    labels_to_y,
    summarize_result,
    tune_on_validation,
)
from ml.extract_embeddings import EmbeddingSet
from ml.train_text import TextFeatures


def fuse_features(text_X, text_ids: Sequence[str], image_X: np.ndarray,
                  image_ids: Sequence[str], *, dtype: str = "float64",
                  order: Sequence[str] = ("text", "image")):
    """Return CSR [text | image] after verifying both blocks describe the same rows."""
    from scipy import sparse

    if list(order) != ["text", "image"]:
        raise DataContractError("fusion order must be [text, image]")
    if list(text_ids) != list(image_ids):
        raise SampleOrderError("text and image rows differ in sample_id or order")
    if text_X.shape[0] != len(text_ids) or image_X.shape[0] != len(image_ids):
        raise SampleOrderError("feature rows do not match their sample_id lists")
    if image_X.ndim != 2:
        raise DataContractError("image block must be 2-D")
    dt = np.dtype(dtype)
    text_block = sparse.csr_matrix(text_X, dtype=dt)
    image_block = sparse.csr_matrix(np.asarray(image_X, dtype=dt))
    fused = sparse.hstack([text_block, image_block], format="csr", dtype=dt)
    if fused.shape != (len(text_ids), text_block.shape[1] + image_block.shape[1]):
        raise DataContractError("unexpected fused shape")
    return fused


def run_multimodal(dataset: Dataset, cfg: dict[str, Any], text: TextFeatures,
                   emb_train: EmbeddingSet, emb_val: EmbeddingSet) -> dict[str, Any]:
    train, val = dataset.rows("train"), dataset.rows("validation")
    fusion = cfg["fusion"]
    X_train = fuse_features(text.X_train, text.train_ids, emb_train.matrix, emb_train.sample_ids,
                            dtype=fusion["dtype"], order=fusion["order"])
    X_val = fuse_features(text.X_val, text.val_ids, emb_val.matrix, emb_val.sample_ids,
                          dtype=fusion["dtype"], order=fusion["order"])
    if text.train_ids != [s.sample_id for s in train] or text.val_ids != [s.sample_id for s in val]:
        raise SampleOrderError("features are not aligned with the dataset split order")
    positive = cfg["selection"]["positive_label"]
    tune = tune_on_validation(X_train, labels_to_y(train, positive),
                              X_val, labels_to_y(val, positive), cfg)
    result = summarize_result("multimodal", tune, feature_dim=X_train.shape[1],
                              train_ids=text.train_ids, val_ids=text.val_ids,
                              is_fixture=dataset.is_fixture)
    result["fusion"] = {"order": list(fusion["order"]), "dtype": fusion["dtype"],
                        "text_dim": text.dim, "image_dim": int(emb_train.matrix.shape[1])}
    return result
