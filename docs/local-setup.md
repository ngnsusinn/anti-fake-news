# Cài đặt và chạy Anti Fake News trên máy local

Dự án gồm API FastAPI, tiện ích Chromium Manifest V3, mã xử lý dữ liệu và pipeline ML. Để thử toàn bộ luồng nhập bài, chọn ảnh và nhận kết quả trên trình duyệt, bắt đầu với **Backend mock + Extension**. Khi cần thử suy luận, chuẩn bị thêm CLIP và bundle Multimodal.

## 1. Chuẩn bị môi trường

Các lệnh chính dùng **PowerShell trên Windows x64** và **Python 3.13**. Cần thêm Git và Chrome hoặc trình duyệt Chromium hỗ trợ tiện ích unpacked. Node.js và npm chỉ cần cho kiểm thử Chromium tự động. Extension có thể nạp trực tiếp từ mã nguồn.

```powershell
git clone https://github.com/ngnsusinn/anti-fake-news.git
Set-Location anti-fake-news
py -3.13 -m venv .venv
$AfnPython = (Resolve-Path ./.venv/Scripts/python.exe).Path
& $AfnPython -m pip install -r backend/requirements.txt
& $AfnPython -m pip check

if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Nếu repo và `.venv` đã có, chạy từ gốc repo và dùng lại môi trường Python 3.13 đang hoạt động. Khi mở PowerShell mới, khai báo lại `$AfnPython` bằng lệnh `Resolve-Path` ở trên. Trên Linux/macOS, tạo môi trường bằng `python3.13 -m venv .venv` và dùng `.venv/bin/python` (hoặc `../.venv/bin/python` khi đứng trong `backend/`). Xem ghi chú cài wheel CPU theo hệ điều hành trong [môi trường ML](ml-environment.md).

## 2. Khởi động Backend ở chế độ mock

Tạo một token cho máy local bằng lệnh dưới đây. Dán giá trị vào dòng `AFN_DEMO_TOKEN=` trong `.env` để Backend và script đóng gói Extension cùng đọc. Giữ `.env` và gói Extension trên máy của bạn.

```powershell
& $AfnPython -c "import secrets; print(secrets.token_urlsafe(32))"
```

Mở `.env` trong trình soạn thảo và đặt các trường sau. `<token-vua-tao>` là chỗ điền token.

```dotenv
AFN_HOST=127.0.0.1
AFN_PORT=8000
AFN_ENVIRONMENT=dev
AFN_PREDICTOR_MODE=mock
AFN_DEMO_TOKEN=<token-vua-tao>
```

Từ gốc repo, chạy Backend và giữ terminal mở.

```powershell
Push-Location backend
try { & $AfnPython -m app } finally { Pop-Location }
```

Trong terminal khác, chạy `curl.exe -i http://127.0.0.1:8000/health`. Kỳ vọng HTTP 200, `model_ready: true` và header `X-AFN-Inference-Mode: mock`. Swagger UI nằm tại [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Dùng **Ctrl+C** ở terminal Backend để dừng dịch vụ. Backend đọc `.env` tại gốc repo và ưu tiên biến môi trường đã đặt trong tiến trình.

## 3. Nạp Extension và thử với một bài mẫu

1. Chạy `& $AfnPython scripts/package_extension.py`. Mở `chrome://extensions`, bật **Developer mode**, chọn **Load unpacked**, rồi chọn thư mục `release/extension/`.
2. Từ gốc repo, mở một terminal riêng, khai báo lại `$AfnPython` và chạy lệnh dưới đây để phục vụ trang mẫu qua loopback.

   ```powershell
   & $AfnPython -m http.server 8765 --bind 127.0.0.1 --directory tests/fixtures/pages
   ```

3. Mở [bài mẫu](http://127.0.0.1:8765/article.html) và bấm biểu tượng **Anti Fake News**.
4. Bấm **Phân tích** để popup lấy văn bản và ảnh từ bài mẫu. Backend mock trả điểm `42%` và nhãn `Real` kèm dòng **Kết quả giả lập**.

Nếu thư mục đầu ra đã chứa bản cũ, dùng `--output cache/extension-next` để tạo bản mới rồi nạp thư mục đó.

## 4. Chạy ML và suy luận bằng bundle

### Thử pipeline Train/Validation

Từ gốc repo, cài thêm dependency ML vào cùng môi trường và tạo dữ liệu tổng hợp. Lệnh smoke text-only có thể chạy offline ngay sau khi cài dependency.

```powershell
& $AfnPython -m pip install -r backend/requirements.txt -r ml/requirements.txt
& $AfnPython -m pip check
& $AfnPython -m ml.fixtures --out cache/ml-fixture
& $AfnPython -m ml.run_experiments --manifest cache/ml-fixture/manifest.jsonl --split cache/ml-fixture/split.csv --configs text-only --offline
```

Kết quả ở `cache/runs/<run-id>/results.json`, với nhãn `FIXTURE_SMOKE_NOT_RESEARCH`. Dùng cặp file trong lệnh trên để chạy Train/Validation. Các file `*-unlocked.*` do fixture sinh ra dành cho kiểm thử cơ chế khóa Test.

### Chuẩn bị CLIP và thử đủ ba cấu hình

Dùng cùng `HF_HOME` cho phiên tải checkpoint, phiên ML và terminal chạy Backend. Lệnh đầu cần mạng nếu cache còn trống. Lệnh thứ hai xác nhận cache dùng được offline.

```powershell
$env:HF_HOME = Join-Path (Get-Location).Path 'cache/huggingface'
& $AfnPython scripts/smoke_clip.py
& $AfnPython scripts/smoke_clip.py --offline
& $AfnPython -m ml.run_experiments --manifest cache/ml-fixture/manifest.jsonl --split cache/ml-fixture/split.csv --offline
```

Khi bỏ `--configs text-only`, runner chạy Text-only, Image-only và Multimodal. Với dữ liệu nghiên cứu, dùng manifest JSONL, split CSV và ảnh do DATA bàn giao cho Train/Validation. Xem [pipeline ML](ml-pipelines.md), [hợp đồng dữ liệu](data-contract.md) và [quy trình tái dựng dữ liệu](rebuild-data.md). Payload Test được giữ riêng theo [quy trình freeze #49](https://github.com/ngnsusinn/anti-fake-news/issues/49).

### Dùng bundle tổng hợp để thử suy luận end-to-end

Từ gốc repo, sau khi đã có cache CLIP, xuất bundle và thử bộ nạp.

```powershell
& $AfnPython -m ml.export_artifacts --fixture --offline
& $AfnPython scripts/smoke_bundle.py --bundle cache/ml-fixture-bundles/multimodal --offline
```

Dừng Backend mock. Sửa các trường sau trong `.env` và giữ token đã tạo. Sau đó khởi động lại Backend như bước 2, trong terminal có `HF_HOME` trỏ tới cùng cache.

```dotenv
AFN_ENVIRONMENT=test
AFN_PREDICTOR_MODE=real
AFN_MODEL_ARTIFACT_PATH=cache/ml-fixture-bundles/multimodal
```

`GET /health` phải trả `model_ready: true` với `X-AFN-Inference-Mode: real`. Thực hiện lại các bước trên Extension. Model ID của bundle tổng hợp có hậu tố `-fixture`. Dùng kết quả này để kiểm tra kỹ thuật.

### Dùng bundle dự án đã chốt

Lấy bundle Multimodal tin cậy cùng SHA-256 của `metadata.json` từ [biên bản đã ký #49](../reports/pre-test-signoff.md). Đối chiếu hash với `Get-FileHash`. Bundle ghi trong biên bản giữ `status: candidate` và `is_fixture: false`. Đặt bundle ở `backend/artifacts/multimodal/` hoặc dùng đường dẫn tuyệt đối. Với cấu hình production, đặt `AFN_ENVIRONMENT=production`, `AFN_PREDICTOR_MODE=real`, `AFN_ALLOW_CANDIDATE_MODEL=true`, `AFN_MODEL_METADATA_SHA256` theo biên bản và `AFN_MODEL_ARTIFACT_PATH` theo vị trí bundle. Dùng cùng token với Extension, đặt `AFN_EXTENSION_ORIGIN` theo ID đã nạp và khởi động Backend với cache CLIP đã ghim. Đặt `$env:HF_HUB_OFFLINE = '1'` trong terminal Backend để dùng cache offline.

Dùng `/health` kiểm tra mode `real` và trạng thái `ready` trước khi gửi bài. Xem [bàn giao Backend](backend-setup.md) để kiểm cache, checksum và chạy smoke trên bundle chính thức.

## 5. Kiểm tra nhanh và xử lý lỗi

Chạy smoke Backend từ gốc repo. Runner tự mở dịch vụ với cổng và token thử nghiệm.

```powershell
Push-Location backend
try {
    & $AfnPython tests/smoke_local.py --mode mock
    & $AfnPython tests/smoke_local.py
} finally { Pop-Location }
```

Lệnh đầu kiểm tra mock trả 200. Lệnh thứ hai kiểm tra real trả 503 khi thiếu bundle, với request hợp lệ. Cả hai kiểm tra request thiếu token trả 401.

Để chạy smoke tự động trên Chromium, cài Node.js và npm, rồi chạy từ gốc repo. Các lệnh cài Playwright trong thư mục tạm của Windows.

```powershell
$AfnPlaywrightDir = Join-Path ([IO.Path]::GetTempPath()) 'afn-extension-playwright'
npm.cmd install --prefix $AfnPlaywrightDir playwright --no-audit --no-fund
& (Join-Path $AfnPlaywrightDir 'node_modules/.bin/playwright.cmd') install chromium
$env:AFN_PLAYWRIGHT_PATH = Join-Path $AfnPlaywrightDir 'node_modules/playwright'
& $AfnPython scripts/test_extension_smoke.py
```

Runner tự tạo các gói tạm với cổng và token của Backend kiểm thử.

| Hiện tượng | Cách kiểm tra |
| --- | --- |
| Extension báo mất kết nối | Mở `/health` trực tiếp. Kiểm Backend đang chạy và địa chỉ trong Extension dùng `127.0.0.1` cùng cổng. Nếu 8000 đã bận, đổi `AFN_PORT` trong `.env`, khởi động lại và cập nhật địa chỉ. |
| `POST /predict` trả 401 | Kiểm `AFN_DEMO_TOKEN` của Backend rồi đóng gói và nạp lại Extension với cùng cấu hình. Khởi động lại Backend nếu đã sửa `.env`. |
| `POST /predict` trả 400 hoặc 413 | Điền thân bài và chọn JPEG/PNG hợp lệ. Tối đa 50.000 ký tự cho thân bài, 10 MiB và 20 triệu pixel cho ảnh, 12 MiB mặc định cho toàn bộ request. |
| `/health` trả 200 nhưng báo `model_ready: false` | Kiểm header `X-AFN-Model-State`. Ở mode real, kiểm thư mục bundle, cache CLIP và giá trị `AFN_ENVIRONMENT`. Fixture chỉ được nạp trong `dev` hoặc `test`. |
| Extension không trích được bài | Thử URL của trang mẫu, mở lại tiện ích sau khi nội dung đã tải, hoặc nhập nội dung và tải ảnh thủ công. |

Nếu cần mở bản trình bày kèm dự án, chạy `& $AfnPython -m http.server 8766 --bind 127.0.0.1 --directory slides` từ gốc repo và mở [127.0.0.1:8766](http://127.0.0.1:8766).
