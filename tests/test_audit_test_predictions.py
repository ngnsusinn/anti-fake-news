"""Synthetic checks for the post-Test QA audit. No model or research rows."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_test_predictions import audit, digest


class TestPredictionAudit(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.paths = [Path(temp.name) / name for name in ("freeze", "metrics", "predictions", "locked", "qa")]
        names = ("text-only", "image-only", "multimodal")
        locked = b"sample_id,split,group_id\na,train,g-a\n,test,g-b\n,test,g-c\n"
        qa = locked.replace(b",test,g-b", b"b,test,g-b").replace(b",test,g-c", b"c,test,g-c")
        freeze = {
            "schema": "afn-model-freeze-v1", "evidence_kind": "VALIDATION_ONLY",
            "created_at": "2026-01-01T00:00:00Z", "blockers": [],
            "protocol": {"status": "locked", "refit_on_train_and_validation": False},
            "label_map": {"0": "real", "1": "fake"},
            "data": {"test_locked_rows": 2, "split_sha256": digest(locked)},
            "configurations": {
                name: {"model_id": name, "model_version": name + "-1", "C": 1,
                       "threshold": 0.5, "is_fixture": False}
                for name in names
            },
        }
        record_hash = digest(json.dumps(freeze, sort_keys=True, separators=(",", ":")).encode())
        freeze.update(status="signed", signoffs={
            role: {"by": role, "record_sha256": record_hash, "at": "2026-01-01T01:00:00Z"}
            for role in ("ml", "qa")
        })
        freeze_bytes = json.dumps(freeze).encode()
        self.rows = []
        for sample, label in (("b", "fake"), ("c", "real")):
            self.rows.append({
                "sample_id": sample, "group_id": "g-" + sample, "source_label": label,
                "predictions": {
                    name: {"label": "fake" if name == "multimodal" else label,
                           "fake_score": 0.5 if label == "fake" or name == "multimodal" else 0.3,
                           "model_version": name + "-1"}
                    for name in names
                },
            })
        perfect_class = {"precision": 1, "recall": 1, "f1": 1, "support": 1}
        perfect = {
            "accuracy": 1, "macro_f1": 1,
            "per_class": {"fake": perfect_class, "real": perfect_class},
            "confusion_matrix": {"labels": ["fake", "real"], "rows_true_cols_pred": [[1, 0], [0, 1]]},
        }
        multimodal = {
            "accuracy": 0.5, "macro_f1": 1 / 3,
            "per_class": {"fake": {"precision": 0.5, "recall": 1, "f1": 2 / 3, "support": 1},
                          "real": {"precision": 0, "recall": 0, "f1": 0, "support": 1}},
            "confusion_matrix": {"labels": ["fake", "real"], "rows_true_cols_pred": [[1, 0], [1, 0]]},
        }
        self.metrics = {
            "schema": "afn-test-metrics-v1", "evidence_kind": "TEST_FINAL", "split": "test", "refit": False,
            "labels": ["fake", "real"], "positive_label": "fake",
            "freeze": {"record_sha256": record_hash, "status": "signed", "signed_by": {"ml": "ml", "qa": "qa"}},
            "created_at": "2026-01-01T02:00:00Z",
            "runs": [{"created_at": "2026-01-01T02:00:00Z", "reason": "first run"}],
            "inputs": {"freeze_sha256": digest(freeze_bytes), "qa_split_sha256": digest(qa),
                       "locked_split_sha256": digest(locked)},
            "n_test": 2, "n_groups": 2, "class_support": {"fake": 1, "real": 1},
            "configurations": {name: {**selected, **deepcopy(multimodal if name == "multimodal" else perfect)}
                               for name, selected in freeze["configurations"].items()},
            "delta_macro_f1_mm_minus_text": 1 / 3 - 1,
        }
        for index, contents in ((0, freeze_bytes), (3, locked), (4, qa)):
            self.paths[index].write_bytes(contents)
        self.write_predictions()
        self.write_metrics()

    def write_predictions(self):
        payload = ("\n".join(json.dumps(row) for row in self.rows) + "\n").encode()
        self.paths[2].write_bytes(payload)
        self.metrics["inputs"]["predictions_sha256"] = digest(payload)
        self.metrics["runs"][-1]["predictions_sha256"] = digest(payload)

    def write_metrics(self):
        self.paths[1].write_text(json.dumps(self.metrics), encoding="utf-8")

    def test_recomputes_all_configurations_and_negative_delta(self):
        result = audit(*self.paths)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["n_test"], 2)
        self.assertAlmostEqual(result["delta_macro_f1_mm_minus_text"], -2 / 3)

    def test_rejects_prediction_checksum_mismatch(self):
        self.paths[2].write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "checksums"):
            audit(*self.paths)

    def test_rejects_duplicate_id_even_with_updated_hash(self):
        self.rows.append(self.rows[0])
        self.write_predictions()
        self.write_metrics()
        with self.assertRaisesRegex(ValueError, "ID/group"):
            audit(*self.paths)

    def test_rejects_label_inconsistent_with_threshold(self):
        self.rows[0]["predictions"]["image-only"]["label"] = "real"
        self.write_predictions()
        self.write_metrics()
        with self.assertRaisesRegex(ValueError, "predicted label"):
            audit(*self.paths)

    def test_rejects_tampered_image_metrics(self):
        self.metrics["configurations"]["image-only"]["accuracy"] = 0
        self.write_metrics()
        with self.assertRaisesRegex(ValueError, "reported score"):
            audit(*self.paths)

    def test_rejects_run_before_qa_signature(self):
        self.metrics["created_at"] = self.metrics["runs"][0]["created_at"] = "2026-01-01T00:30:00Z"
        self.write_metrics()
        with self.assertRaisesRegex(ValueError, "run log"):
            audit(*self.paths)

    def test_rejects_undocumented_rerun(self):
        self.metrics["runs"].insert(0, dict(self.metrics["runs"][0], created_at="2026-01-01T01:30:00Z"))
        self.write_metrics()
        with self.assertRaisesRegex(ValueError, "reason"):
            audit(*self.paths)
