# Gói mô hình `afn-model-bundle-v1`: bàn giao cho Backend (#24, #37)

Trạng thái: **định dạng đề xuất bởi ML (AFN-035)**, chờ Integration (#24) và Backend review.
Hiện chỉ có **gói fixture** (huấn luyện trên dữ liệu tổng hợp, `is_fixture: true`) để Backend
viết loader và predictor. Gói ứng viên thật được xuất bằng cùng lệnh sau #34. Gói fixture
**không** được dùng làm bằng chứng nghiệm thu artifact thật hay kết quả mô hình.

## 1. Tạo gói trên máy bạn

Gói không commit (`.gitignore` chặn `artifacts/`). Mỗi người tự sinh, mất khoảng 10 giây, cần cache CLIP từ AFN-006:

```sh
.venv/bin/python -m ml.export_artifacts --fixture --offline
.venv/bin/python scripts/smoke_bundle.py --bundle backend/artifacts/multimodal --offline
```

Kết quả:

```
backend/artifacts/
  label_map.json          {"0": "real", "1": "fake"}, positive_label fake
  export-report.json      parity khi xuất (Validation), model_version từng gói
  text_only/  image_only/  multimodal/
```

Demo dùng `multimodal`, nên đặt trong `.env`: `AFN_MODEL_ARTIFACT_PATH=backend/artifacts/multimodal`.

## 2. Nội dung một gói

| File | Nội dung |
| --- | --- |
| `metadata.json` | Mọi thông tin bên dưới, kèm `files` (sha256 + bytes của từng file) |
| `classifier/coef.npy`, `classifier/intercept.npy` | Logistic Regression, float64, shape `(1, feature_dim)` và `(1,)` |
| `text/vocabulary.json`, `text/idf.npy` | TF-IDF đã fit trên Train (chỉ có ở text-only và multimodal) |

**Không dùng pickle/joblib.** Mảng được nạp bằng `allow_pickle=False`, nên nạp gói không bao giờ chạy code lạ.
**CLIP không được đóng gói** (`image.packaged: false`). Metadata ghim repo, revision, hash processor
và `preprocess_version`; service phải nạp đúng encoder đó từ cache Hugging Face.

Các trường chính của `metadata.json`:

| Trường | Ý nghĩa |
| --- | --- |
| `configuration` | `text-only` / `image-only` / `multimodal` |
| `model_id`, `model_version` | Trả thẳng trong `PredictResponse`. Version chứa hash nội dung; gói fixture có hậu tố `-fixture` |
| `status` | `candidate` cho tới khi #49 khóa (`frozen`) |
| `is_fixture`, `evidence_kind` | `true` và `FIXTURE_SMOKE_NOT_RESEARCH` với gói fixture |
| `classes`, `label_map`, `positive_label` | `[0, 1]`, `{"0": "real", "1": "fake"}`, `fake` |
| `threshold`, `threshold_comparison` | Ngưỡng chọn trên Validation; `fake` nếu `fake_score >= threshold` |
| `feature_dim`, `text.dim`, `image.dim`, `fusion` | Số chiều và thứ tự ghép `[text, image]`, float64 |
| `preprocess_version` | Phải bằng `PREPROCESS_VERSION` của service, nếu không thì từ chối |
| `training` | Seed, số mẫu, hash manifest/split/config, hash thứ tự Train |
| `test_predictions_included` | Luôn `false` |

## 3. Code tích hợp (gợi ý cho #24/#37)

`backend/app/model_bundle.py` là thư viện thuần: không chứa FastAPI và không quản lý vòng đời.
Loader (#24) bọc nó vào lifecycle và adapter; predictor (#37) gọi `predict`.

```python
from app.model_bundle import BundleError, check_encoder_identity, load_bundle
from app.preprocessing import load_image_rgb

# Startup, một lần (#24). Bất kỳ lỗi nào cũng cho state=error và /predict trả 503.
bundle = load_bundle(settings.model_artifact_path, expected_configuration="multimodal")
encoder = ClipImageEncoder(offline=True)          # hiện nằm ở ml/extract_embeddings.py
check_encoder_identity(bundle, encoder.identity, encoder.dim)
# warm-up: bundle.predict("warm up", "warm up text", encoder.encode([load_image_rgb(png)]))

# Mỗi request (#37), sau khi validation (#22/#23) đã cho bytes ảnh hợp lệ:
emb = encoder.encode([load_image_rgb(inputs.image_bytes)])
pred = bundle.predict(inputs.title, inputs.text, emb)
# -> pred.label, pred.fake_score, pred.text_truncated, pred.model_id, pred.model_version
```

Ánh xạ lỗi:

| Lỗi | HTTP |
| --- | --- |
| `BundleError` khi startup (thiếu file, sai checksum, sai số chiều, sai `label_map`, lệch encoder, lệch `preprocess_version`) | 503 `model_not_ready` |
| `PreprocessingError` (`EmptyTextError`, `InvalidImageError`) | 400 `invalid_input` |
| `NonFiniteEmbeddingError`, `BundleError` lúc chấm điểm | 503 (lỗi mô hình) |

Thông điệp của `BundleError` không chứa đường dẫn hay nội dung file.

`ClipImageEncoder` hiện nằm trong `ml/`. Muốn backend import thì cần repo root trên `sys.path`
(xem `scripts/smoke_bundle.py`), hoặc #24 chuyển lớp này vào `backend/app/`. Quyết định cách nào thuộc #24.

## 4. Đã kiểm tra

- **Parity khi xuất:** nạp lại gói từ đĩa, tính lại điểm Validation từ text thô và embedding, so với
  `predict_proba` của scikit-learn: sai lệch tối đa 0,0, nhãn trùng 100% cho cả 3 gói (ngưỡng cho phép 1e-9).
- `tests/test_model_bundle.py` (25 test): TF-IDF của gói khớp `TfidfVectorizer.transform` trên text chưa thấy;
  `text_truncated` đúng; gói bị sửa coef, nhét pickle, sai threshold/label_map/`preprocess_version`/thứ tự ghép,
  thiếu file, lệch encoder đều bị từ chối; thông điệp lỗi không lộ đường dẫn; export từ chối dữ liệu có Test.
- `scripts/smoke_bundle.py` (macOS M1, CPU, CLIP thật, input tổng hợp, sau khi nạp model):

| Gói | Nạp gói + CLIP | 1 request (trung vị / max, 20 lượt) |
| --- | --- | --- |
| multimodal | ~4,0 s | 42,5 / 53,1 ms |
| text-only | ~0,7 s | 0,2 / 0,4 ms |

## 5. Còn mở

| Việc | Owner |
| --- | --- |
| Duyệt định dạng; chốt `metadata.schema.json` cho #24. Lưu ý `.gitignore` có `artifacts/` sẽ chặn luôn file schema nếu đặt ở `backend/artifacts/` | Integration (#24) |
| Chốt nơi đặt `ClipImageEncoder` cho backend | Integration (#24) |
| Xuất gói ứng viên thật từ split đã audit | ML (#35, sau #34) |
| Parity offline–online qua predictor thật | ML (#36) + Backend (#37) |
