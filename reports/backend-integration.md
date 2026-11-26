# Báo cáo Kiểm thử Tích hợp Backend — AFN-039

Ngày chạy: **26/11/2026** (giờ địa phương). Môi trường: **Windows 11 x64 (`Windows-11-10.0.26300-SP0`)**, **Python 3.13.1** (`.venv\issue9`), CPU (`torch 2.15.0+cpu`, 4 threads), chế độ hoàn toàn offline (`HF_HUB_OFFLINE=1`).

> **Nguyên tắc bằng chứng:**
> - Báo cáo tách rõ **nhóm kiểm thử fixture tổng hợp** với **nhóm kiểm thử candidate Multimodal thật (`is_fixture: false`) + CLIP thật**.
> - **Không đọc dữ liệu Test nghiên cứu** trong bất kỳ bước nào.
> - **Không gọi API AI bên ngoài**; mọi lời gọi suy luận chạy cục bộ trên CPU từ cache offline.

## 1. Tổng hợp lệnh chạy và kết quả

| Nhóm kiểm thử | Lệnh chạy | Kết quả | Loại bằng chứng |
| --- | --- | --- | --- |
| Unit + API contract + CORS + Adapter | `Push-Location backend; ..\.venv\issue9\Scripts\python.exe -m pytest -q; Pop-Location` | **196 passed** (4,25 s) | Fixture/unit |
| Loader + Bundle + Parity + Integration (kèm CLIP & candidate thật) | `$env:AFN_CLIP_TESTS='1'; $env:HF_HUB_OFFLINE='1'; .\.venv\issue9\Scripts\python.exe -m pytest -v tests/test_model_loader.py tests/test_model_bundle.py tests/test_inference_parity.py tests/integration/test_predict.py` | **77 passed, 0 skipped** (80,60 s) | Fixture + Candidate thật (`multimodal-20261125-105d5f14e79a`) trên đầu vào tổng hợp |
| Smoke CLIP đã ghim (online & offline) | `.\.venv\issue9\Scripts\python.exe scripts/smoke_clip.py && .\.venv\issue9\Scripts\python.exe scripts/smoke_clip.py --offline` | **16/16 check PASS** (offline median 99,7 ms/ảnh) | CLIP thật trên ảnh tổng hợp |
| Smoke bundle candidate thật | `.\.venv\issue9\Scripts\python.exe scripts/smoke_bundle.py --bundle backend/artifacts/multimodal --offline --repeat 20` | **PASS** (load 10,487 s; median 108,7 ms; max 193,3 ms) | Candidate thật trên đầu vào tổng hợp |
| CLI Parity (`ml.inference_parity`) với hook Backend #37 | `python -m ml.inference_parity --bundle-root backend/artifacts --manifest <synth> --split <synth> --image-root <synth> --configurations multimodal --predictor app.predictor:load_for_parity --offline` | **PASS**: `n=8`, `max|diff|=2.30e-07 <= 1e-6`, `labels_equal=True`, `truncated_equal=True`, `identity_equal=True`, `errors=0` | Candidate thật + CLIP thật + Predictor thật trên 8 mẫu Validation tổng hợp |
| Smoke HTTP thực tế `127.0.0.1:8000` (`python -m app`) | Khởi động Uvicorn `demo`/`real`, kiểm tra `/health`, CORS, `401/400/413`, 3 ca mẫu và 20 lượt `/predict` | **PASS** (startup 13,014 s; server median 106,0 ms, HTTP median 113,7 ms, log sạch) | Candidate thật + CLIP thật trên đầu vào tổng hợp |
| Toàn vẹn dependency & định dạng diff | `.\.venv\issue9\Scripts\python.exe -m pip check` và `git -c core.safecrlf=false diff --check` | **PASS** (`No broken requirements found`, 0 lỗi whitespace) | Hygiene |

## 2. Ma trận ca tích hợp và lỗi hợp đồng (`tests/integration/test_predict.py`, `backend/tests/test_cors.py`)

| Hạng mục / Truy vết | Ca kiểm thử đã xác minh | Trạng thái | Ghi chú kiểm chứng |
| --- | --- | --- | --- |
| Luồng thành công (T05, T07, FR-05) | Startup nạp 1 lần + warm-up → `/health` `model_ready: true` → `POST /predict` trả đủ `request_id`, `label`, `fake_score` hữu hạn `[0,1]`, `model_id`, `model_version`, `processing_time_ms >= 0`, `text_truncated` | **PASS** | Xác minh cả trên fixture lẫn candidate thật `multimodal-20261125-105d5f14e79a` + CLIP offline |
| Parity offline–online (#36/#37) | Đối chiếu từng mẫu qua HTTP `/predict` và qua `app.predictor:load_for_parity` với `OfflineReference`: EXIF orientation 6, PNG RGBA, body 1.700–1.800 từ (`text_truncated=true`), title rỗng | **PASS** | `max|Δscore| <= 2.30e-07` (ngưỡng `1e-6`), khớp 100% nhãn, truncation và định danh |
| Xác thực token `401` (T06, #22/#38) | Thiếu/sai/trùng `X-Demo-Token`, hoặc token chưa cấu hình → `401 invalid_token`, `request_id: null`, từ chối trước khi đọc body; vẫn kiểm tra kể cả khi `Origin` khớp CORS | **PASS** | Đã kiểm chứng cả trong pytest lẫn HTTP thật trên `127.0.0.1:8000` |
| Validation đầu vào `400` (T04, T05, #22/#23) | UUID sai, text trắng, text chỉ có URL (rỗng sau `preprocess_text`), `title > 500`, `text > 50.000`, MIME lệch byte thực, ảnh hỏng, gửi JSON → `400 invalid_input`, không trả 422, `/health` giữ `ready` | **PASS** | Echo `request_id` khi parse an toàn; ẩn token/path/nội dung bài báo |
| Giới hạn kích thước `413` (T05, #22) | Ảnh > 10 MiB và tổng body > 12 MiB → `413 request_too_large`; mọi `SpooledTemporaryFile` đều được đóng sạch sau lỗi và sau thành công | **PASS** | Kiểm chứng trực tiếp qua `SpooledTemporaryFile` tracker và HTTP thật |
| Chưa sẵn sàng / lỗi startup `503` (T08, #24/#38) | Thiếu file, sai schema/checksum/dim/classes/label_map/encoder/dtype, lỗi warm-up, hoặc bundle fixture trong `demo` → `health` báo `model_ready: false`, `X-AFN-Model-State: error`, `/predict` trả `503 model_not_ready`, không chạy pipeline nạp dở, không fallback mock | **PASS** | Xác minh `encoder.close()` được gọi khi warm-up thất bại |
| CORS và trình duyệt (T08, #38) | Preflight `OPTIONS` & `GET/POST` từ `AFN_EXTENSION_ORIGIN` hợp lệ nhận `Access-Control-Allow-Origin` và đọc được header `X-AFN-*` + JSON lỗi `400/401/413/503`; origin lạ hoặc khi chưa cấu hình bị từ chối preflight `400` và không nhận ACAO | **PASS** | Phân biệt rõ CORS là chính sách trình duyệt, không thay thế token |
| Nhiều request quy mô demo & dọn tài nguyên (#39) | 10 request tuần tự xen kẽ lỗi `400` + 8 request đồng thời qua 4 luồng (tuần tự hóa bằng `RLock`) + 20 lượt HTTP sống liên tiếp; điểm nhất quán, không gọi `fit()`, đóng `SpooledTemporaryFile` và `encoder.close()` khi shutdown | **PASS** | Không rò rỉ tệp tạm hay tham chiếu encoder sau shutdown |

## 3. Lỗi phát hiện và ghi nhận bàn giao cho ML (không sửa vượt ranh giới file)

- **Phát hiện ở `ml/inference_parity.py:293` (ML-owned, #36):** Trong hàm `_fixture_inputs()`, harness gán `"experiment_config_sha256": "fixture"` thay vì chuỗi SHA-256 64 ký tự hex. Khi chạy `python -m ml.inference_parity --fixture --offline --configurations multimodal --predictor app.predictor:load_for_parity`, bộ kiểm tra schema `backend/artifacts/metadata.schema.json` trong `app.model_loader.load_predictor` từ chối đúng theo thiết kế (`BundleError: bundle metadata does not match the schema`).
  - **Ảnh hưởng:** Không ảnh hưởng đến bundle tạo bởi `ml.export_artifacts` hay candidate thật `backend/artifacts/multimodal` (cả hai đều có SHA-256 64 ký tự hợp lệ và PASS qua `--bundle-root`).
  - **Đề xuất chủ sở hữu:** ML (`0xDa1Vu`) cập nhật `_fixture_inputs` trong `ml/inference_parity.py` dùng SHA-256 hợp lệ (ví dụ SHA-256 thật của `configs/experiment.yaml`) nếu muốn `--fixture` tương thích trực tiếp với `app.model_loader.load_predictor`.

## 4. Blocker / điều kiện còn lại để nghiệm thu Done (#37, #38, #39)

| Hạng mục còn mở | Chủ sở hữu | Tình trạng |
| --- | --- | --- |
| Chạy lại `ml.inference_parity --predictor app.predictor:load_for_parity` trên tập **Validation thật** (`data/private/ml-v2/train-validation`, 32 mẫu — không đọc Test) | ML (`0xDa1Vu`) + Backend (`Phuc1232`) | Chờ bàn giao cục bộ thư mục `data/private/ml-v2/train-validation` (hiện được `.gitignore`, chưa có trên máy checkout này) |
| Xác nhận review liên vai trò cho #37, #38, #39 (và review tồn đọng #24/#36) | ML (`0xDa1Vu`), Extension, Repo Owner (`ngnsusinn`) | Chưa có review/approval trên PR/GitHub |
| Xác nhận bộ chia `ml-v2` và khóa mô hình demo | DATA / QA (#29, #49) | Candidate hiện ở trạng thái `candidate` (`VALIDATION_ONLY`), chưa `frozen`; Test vẫn khóa |
| Kiểm thử end-to-end trình duyệt thật với Chromium Extension | Extension + QA (#40–#43) | Ngoài phạm vi Backend #37–#39 |
