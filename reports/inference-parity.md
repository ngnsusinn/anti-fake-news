# AFN-036 · Tương đương suy luận offline–online

Trạng thái: **harness đã chạy trên gói ứng viên thật (#35, dataset ml-v2) trên Validation: PASS**.
Predictor online vẫn là `ReferenceBundlePredictor` (tham chiếu của harness). Muốn nghiệm thu cần predictor thật
từ #37, đo trên máy demo, và Backend review. Báo cáo này kiểm tra tính tương đương, **không** phải chất lượng mô hình.

## 1. So sánh hai đường chạy nào

| Đường | Các bước |
| --- | --- |
| Offline (phía train) | `preprocess_text(title, body)`; `TfidfVectorizer` của scikit-learn dựng lại từ vocabulary/IDF trong gói. Bytes ảnh qua `load_image_rgb`, encoder theo lô `image_features.batch_size`, rồi L2. Ghép `hstack` theo `fusion.order`, tính `LogisticRegression.predict_proba`, lấy cột có class mà `label_map` ứng với `fake`, rồi so với threshold |
| Online (phía phục vụ) | `PredictorInput` dạng request thật (UUID, title, text, bytes ảnh JPEG/PNG gốc), gọi một `Predictor` bất kỳ, nhận `PredictionResult` (kiểm schema strict) |

Đường offline **không** gọi `ModelBundle.features` hay `ModelBundle.fake_scores`. Nếu cách bundle tính điểm
bị lệch thì harness vẫn phát hiện được.

## 2. Sai số và tiêu chí PASS

Mỗi mẫu phải thỏa tất cả các điều sau:

- `|fake_score_online − fake_score_offline| ≤ atol`, mặc định `atol = 1e-6`;
- `label` trùng nhau, và `label` khớp với quy tắc `fake_score ≥ threshold`;
- `text_truncated` trùng nhau (quy tắc 1.500 từ, chỉ tính body);
- `model_id` và `model_version` trùng với metadata của gói.

Các lỗi được xử lý như sau:

- Predictor ném exception, hoặc trả kết quả sai schema (ví dụ NaN, thiếu trường) → FAIL với
  `predictor_error`. `online_score` để `null` và **không thay bằng điểm minh họa**. Báo cáo chỉ ghi tên lớp lỗi, không ghi nội dung exception.
- Encoder lệch revision, processor hoặc `preprocess_version`, hay gói lệch `preprocess_version`
  → `BundleError` trước khi chấm điểm, nên không sinh ra điểm nào.
- Dữ liệu Test bị từ chối (`TestSplitLockedError`). Harness chỉ đọc Validation.

## 3. Kết quả trên fixture (25/11/2026, macOS arm64, Python 3.14.7)

CLIP thật `openai/clip-vit-base-patch32@3d74acf9`, 8 mẫu Validation tổng hợp, predictor là
`ReferenceBundlePredictor` (tham chiếu của harness, **không phải #37**):

| Cấu hình | n | max \|Δscore\| | Nhãn | Truncated | Model ID/version | Kết quả |
| --- | --- | --- | --- | --- | --- | --- |
| text-only | 8 | 0.00e+00 | trùng | trùng | trùng | PASS |
| image-only | 8 | 0.00e+00 | trùng | trùng | trùng | PASS |
| multimodal | 8 | 0.00e+00 | trùng | trùng | trùng | PASS |

Offline encode cả lô 8 ảnh, online encode từng ảnh một (batch 1). Trên máy này, hai cách cho sai lệch đo được bằng 0.
Ngưỡng `1e-6` để dư cho trường hợp CPU hoặc thư viện khác cho sai lệch float32 nhỏ.
Phải đo lại trên máy demo Windows.

## 3b. Kết quả trên gói ứng viên thật (25/11/2026, macOS arm64, Python 3.14.7)

Gói `backend/artifacts/candidates-v2` (#35, `is_fixture: false`), 32 mẫu Validation của dataset ml-v2 (#34),
CLIP thật `openai/clip-vit-base-patch32@3d74acf9`, `afn-preprocess-v1`, atol `1e-6`, predictor
`ReferenceBundlePredictor` (**không phải #37**). Test không được nạp. `evidence_kind: VALIDATION_ONLY`.

| Cấu hình | model_version | n | max \|Δscore\| | Nhãn | Truncated | Model ID/version | Lỗi | Kết quả |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| text-only | `text-only-20261125-275718e3163b` | 32 | 0.00e+00 | trùng | trùng | trùng | 0 | PASS |
| image-only | `image-only-20261125-cd863cbaabf5` | 32 | 0.00e+00 | trùng | trùng | trùng | 0 | PASS |
| multimodal | `multimodal-20261125-105d5f14e79a` | 32 | 0.00e+00 | trùng | trùng | trùng | 0 | PASS |

Đầu vào là ảnh PNG thật đã thu hồi (không phải ảnh tổng hợp); 1/32 mẫu có body bị cắt ở 1.500 từ. Lệnh chạy:

```sh
H=data/private/ml-v2/train-validation
.venv/bin/python -m ml.inference_parity --bundle-root backend/artifacts/candidates-v2 --manifest $H/manifest.jsonl \
    --split $H/split.csv --image-root data --offline --out cache/parity/real-v2.json
```

## 4. Test (`tests/test_inference_parity.py`)

24 test: 23 chạy với `FakeImageEncoder` (test double, không phải CLIP), 1 test CLIP thật chỉ chạy khi đặt `AFN_CLIP_TESTS=1`.

- **PASS mong đợi.** Ba cấu hình trên Validation, và các ca biên dạng request:
  - JPEG có EXIF orientation 6 (ảnh không vuông);
  - PNG RGBA;
  - PNG palette có transparency;
  - body 2.400 từ (bị cắt);
  - text có khoảng trắng hoặc ký tự vô hình;
  - title rỗng.

  Ngoài ra còn kiểm: đảo `label_map` thì `fake_score` phải bằng `1 − P(class 1)`, và đường offline sklearn khớp `ModelBundle` đến `1e-12`.
- **Mutant phải FAIL.** Đây là các predictor cố tình sai, dùng để chứng minh harness phát hiện được lệch:
  - bỏ qua EXIF và nền trắng cho alpha;
  - bỏ qua `label_map`;
  - ghép `[image, text]` thay vì `[text, image]`;
  - không cắt 1.500 từ;
  - trả `model_version` cũ;
  - ném exception;
  - trả NaN.
- **Từ chối:** dữ liệu Test, danh sách mẫu rỗng, encoder khác revision, gói lệch `preprocess_version`.

## 5. Cách chạy

```sh
# Fixture + CLIP đã cache (tự xuất gói fixture tạm, không ghi vào backend/artifacts)
.venv/bin/python -m ml.inference_parity --fixture --offline --out cache/parity/fixture.json

# Nghiệm thu thật: gói ứng viên #35 trên Validation, predictor thật #37
.venv/bin/python -m ml.inference_parity --bundle-root <export-dir> \
    --manifest <train-validation>/manifest.jsonl --split <train-validation>/split.csv \
    --image-root <train-validation>/images --offline \
    --predictor <module>:<factory> --out reports/inference-parity.json
```

`<factory>(bundle_dir) -> Predictor` là điểm cắm cho Backend (#37). Lệnh thoát với mã 1 nếu có cấu hình FAIL.

## 6. Còn thiếu để Done #36

| Việc | Owner | Phụ thuộc |
| --- | --- | --- |
| ~~Chạy harness với gói ứng viên thật trên Validation~~ (xong, mục 3b) | ML | #34, #35 (chờ DATA/QA xác nhận ml-v2) |
| Thay `ReferenceBundlePredictor` bằng predictor thật | Backend (Phuc1232) | #24 loader, #37 |
| Đo lại trên máy demo Windows, ghi kết quả vào báo cáo này | ML + Backend | máy demo |
| Review | BACKEND | — |
