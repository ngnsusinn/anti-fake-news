# Báo cáo Smoke `POST /predict` với artifact Multimodal thật — AFN-037

Ngày đo: **26/11/2026** (giờ địa phương). Tài liệu ghi nhận kết quả nối đường suy luận thật
`POST /predict` với gói ứng viên Multimodal (`is_fixture: false`, `status: candidate`) và
encoder CLIP ViT-B/32 đã ghim chạy hoàn toàn cục bộ, offline.

> **Phạm vi bằng chứng:** Mọi đầu vào bài báo/ảnh trong smoke này đều là **dữ liệu tổng hợp
> được phép** (synthetic fixtures). Kết quả xác nhận đúng luồng kỹ thuật, hợp đồng schema và
> độ trễ sau nạp mô hình; **không** đánh giá chất lượng mô hình nghiên cứu và **không** đọc tập Test.

## 1. Môi trường và cấu hình thực thi

| Hạng mục | Giá trị đo thực tế |
| --- | --- |
| Hệ điều hành / CPU | `Windows-11-10.0.26300-SP0` (AMD64, Intel64 Family 6 Model 126, 8 logical CPUs, 11,8 GiB RAM) |
| Python / Runtime | `Python 3.13.1` (`.venv\issue9`), `torch 2.15.0+cpu` (4 threads), `transformers 5.24.0`, `scikit-learn 1.9.1`, `scipy 1.18.1`, `numpy 2.5.5`, `pillow 13.0.0` |
| Cấu hình dịch vụ | `AFN_HOST=127.0.0.1`, `AFN_PORT=8000`, `AFN_ENVIRONMENT=demo`, `AFN_PREDICTOR_MODE=real`, `HF_HUB_OFFLINE=1` |
| Gói ứng viên thật | `backend/artifacts/multimodal` (`model_id: afn-multimodal`, `model_version: multimodal-20261125-105d5f14e79a`, `threshold: 0.7`, `feature_dim: 5512 = 5000 TF-IDF + 512 CLIP`, `is_fixture: false`, `status: candidate`) |
| CLIP đã ghim | `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` (`eval()`, `requires_grad_(False)`, `float32`, nạp từ `cache/huggingface/hub` ở chế độ offline) |
| Tiền xử lý dùng chung | `app.preprocessing` (`PREPROCESS_VERSION = afn-preprocess-v1`) |

## 2. Luồng suy luận đã nối (`backend/app/predictor.py`, `model_loader.py`, `inference_adapter.py`, `main.py`)

1. Startup qua FastAPI `lifespan` gọi `create_adapter` → `app.model_loader.load_predictor` trong threadpool:
   - Xác thực `metadata.schema.json`, SHA-256 và kích thước tất cả file `.npy`/`.json` (`allow_pickle=False`), `classes`, `label_map`, `threshold`, `preprocess_version`, từ chối fixture trong `demo`.
   - Nạp `ClipImageEncoder(offline=True)` và đối chiếu `repo_id`, `revision`, `processor_config_sha256`, `dim=512`, `dtype=float32`.
   - Warm-up bằng PNG tổng hợp 32×32 trước khi chuyển trạng thái `ready`; nếu lỗi ở bất kỳ bước nào thì `close()` giải phóng encoder/predictor và giữ `ModelState.ERROR`.
2. Mỗi yêu cầu `POST /predict`:
   - `LocalCORSMiddleware` → `RequestLimitsMiddleware` (`X-Demo-Token` qua `hmac.compare_digest`, trần tổng body 12 MiB) → `validate_request` (multipart, UUID, text/title, ảnh JPEG/PNG ≤ 10 MiB / ≤ 20 MP, giải mã kiểm tra bằng `load_image_rgb`).
   - `InferenceAdapter.predict` tuần tự hóa qua `RLock`, gọi `BundlePredictor.predict`: `load_image_rgb` → `ClipImageEncoder.encode` → kiểm tra dtype `float32` → `ModelBundle.predict` (`preprocess_text` → TF-IDF cố định từ vựng/IDF → L2 CLIP → `scipy.sparse.hstack([text, image])` → Logistic Regression sigmoid → `label_map` & `threshold >= 0.7`).
   - Không có bất kỳ thao tác `fit()`/`train()` nào trong request (được khẳng định qua monkeypatch test).
   - Đo `processing_time_ms` bằng `perf_counter()` quanh lời gọi `predictor.predict` (loại trừ model load và transport validation).

## 3. Kết quả kiểm tra smoke trực tiếp

### 3.1. Smoke CLIP độc lập (`scripts/smoke_clip.py --offline`)

- **16/16 check PASS** (`dim_measured=512`, `dtype=float32`, `l2_norm=1.0`, `batch_single_max_abs_diff=2.01e-7`, `weights_unchanged=true`).
- Tải từ cache offline: `0,017 s`; nạp model+processor: `0,272 s`; 1 ảnh (20 lượt): trung vị **99,7 ms**, tối đa **112,4 ms**.

### 3.2. Smoke bundle trực tiếp (`scripts/smoke_bundle.py --bundle backend/artifacts/multimodal --offline --repeat 20`)

- Nạp bundle + CLIP: **10,487 s**.
- 20 lượt dự đoán sau nạp: trung vị **108,7 ms**, tối đa **193,3 ms**.

### 3.3. Smoke HTTP thực tế qua `python -m app` trên `http://127.0.0.1:8000`

Khởi động với `AFN_ENVIRONMENT=demo`, `AFN_PREDICTOR_MODE=real`, `AFN_MODEL_ARTIFACT_PATH=backend/artifacts/multimodal`, `HF_HUB_OFFLINE=1` và token tạm:

- **Thời gian startup + warm-up tới `GET /health` `model_ready: true`:** **13,014 s**.
- **Header sẵn sàng:** `X-AFN-Inference-Mode: real`, `X-AFN-Model-State: ready`, `Cache-Control: no-store`.
- **Mẫu đầu vào tổng hợp qua `POST /predict`:**

| Ca mẫu (tổng hợp) | HTTP | `label` | `fake_score` | `text_truncated` | `model_id` / `model_version` | `processing_time_ms` | Round-trip HTTP |
| --- | ---: | --- | ---: | --- | --- | ---: | ---: |
| `short_png` (PNG RGB + title) | 200 | `real` | `0.444902` | `false` | `afn-multimodal` / `multimodal-20261125-105d5f14e79a` | 105 ms | 121,3 ms |
| `exif_jpeg` (JPEG EXIF orientation 6) | 200 | `real` | `0.538846` | `false` | `afn-multimodal` / `multimodal-20261125-105d5f14e79a` | 103 ms | 109,8 ms |
| `rgba_truncated` (PNG RGBA, body 1.700 từ, không title) | 200 | `real` | `0.496681` | `true` | `afn-multimodal` / `multimodal-20261125-105d5f14e79a` | 110 ms | 113,3 ms |

- **Đo 20 lượt `POST /predict` liên tiếp sau nạp mô hình:**
  - `processing_time_ms` phía server: trung vị **106,0 ms** (min **101 ms**, max **115 ms**).
  - Độ trễ HTTP round-trip đầu cuối: trung vị **113,7 ms** (min **105,5 ms**, max **137,7 ms**) — đạt xa dưới mục tiêu 10 giây.
- **Các ca lỗi trên cùng server sống:** thiếu token → `401 invalid_token`; nội dung chỉ có URL (rỗng sau `preprocess_text`) → `400 invalid_input` (echo `request_id`); ảnh > 10 MiB → `413 request_too_large`; `/health` giữ `model_ready: true` sau các lỗi client.
- **Vệ sinh log khi dừng server:** tiến trình Uvicorn dừng sạch (`7` dòng vòng đời), không xuất hiện token, nội dung bài báo, đường dẫn artifact hay traceback.

## 4. Điểm nối parity (#36) và việc còn mở

- Đã cung cấp factory hook `app.predictor:load_for_parity(bundle_dir) -> BundlePredictor` dùng chung `app.model_loader.load_predictor` (xem kiểm chứng parity chi tiết tại [reports/backend-integration.md](backend-integration.md)).
- **Còn mở để Done #37:**
  - Review của vai trò **ML** đối với kết quả smoke và tích hợp `BundlePredictor`/`load_for_parity`.
  - Nghiệm thu cuối trên tập Validation thật `data/private/ml-v2/train-validation` khi gói dữ liệu Validation được bàn giao về máy demo (chỉ dùng Validation, không đọc Test) và xác nhận freeze mô hình ở #49.
