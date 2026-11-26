# Cài và chạy Backend trên máy khác · AFN-054

Gói nguồn chạy FastAPI trên `127.0.0.1` với API v0.2.0, Python 3.13 và CLIP
ViT-B/32 trên CPU. Các bước dưới đây dùng PowerShell trên Windows x64.
Dùng `.venv/bin/python` và `.venv/bin/hf` trên hệ POSIX. Kiểm tra lại
wheel và phiên bản Python theo hệ điều hành/kiến trúc của máy đích.

## 1. Chuẩn bị gói và dependencies

Từ checkout đã đồng bộ, chạy `python scripts/package_backend.py`. Gói ra
mặc định ở `release/backend.zip`. Ghi commit và `Get-FileHash
release/backend.zip -Algorithm SHA256` trong biên bản bàn giao. Dùng
`--output` để chọn tên mới nếu gói đã tồn tại. Gửi gói và checksum qua
kênh đã thống nhất. ZIP chứa danh sách tệp nguồn cố định, gồm cấu hình
mẫu, dependency pins, schema và tài liệu. Bundle, CLIP cache, dữ liệu và
secret được cấp riêng.

Giải nén vào thư mục mới và chạy từ gốc của thư mục đã giải nén.

```powershell
python -m venv .venv
$AfnPython = (Resolve-Path ./.venv/Scripts/python.exe).Path
& $AfnPython -m pip install -r backend/requirements.txt -r ml/requirements.txt
& $AfnPython -m pip check
```

Để cài trên máy offline, tạo wheelhouse trên máy có mạng cùng hệ điều hành,
kiến trúc và phiên bản Python. Dùng nguồn package được nhóm phê duyệt và
ghi hash các wheel khi chuyển sang máy đích.

```powershell
& $AfnPython -m pip download --only-binary=:all: --dest ./wheelhouse -r backend/requirements.txt -r ml/requirements.txt
# Trên máy đích sau khi tạo venv, với wheelhouse đã đối chiếu checksum.
& $AfnPython -m pip install --no-index --only-binary=:all: --find-links ./wheelhouse -r backend/requirements.txt -r ml/requirements.txt
& $AfnPython -m pip check
```

Nếu pip thiếu wheel cho máy đích, dùng môi trường tương thích đã được nhóm
kiểm tra và ghi lại sai lệch. Giữ nguyên pins khi nghiệm thu. Cấu hình
tham chiếu và hướng dẫn CPU cho Linux có trong tài liệu môi trường ở repo.
[Môi trường ML](https://github.com/ngnsusinn/anti-fake-news/blob/main/docs/ml-environment.md)

## 2. Chuẩn bị bundle đã khóa và CLIP

**Bundle dự án.** Lấy thư mục Multimodal đã khóa từ ML/Backend qua kho
được cấp quyền. Lấy SHA-256 của `metadata.json` và model version từ
biên bản AFN-049 độc lập với thư mục tải về. Đặt thư mục dưới
`backend/artifacts/multimodal` hoặc cấu hình đường dẫn tuyệt đối. Kiểm
SHA-256 metadata bằng `Get-FileHash` trước khi nạp. Loader xác thực
schema `afn-model-bundle-v1`, hash/kích thước các file được liệt kê trong
metadata, encoder và preprocessing. Hồ sơ AFN-049 hiện là `signed`,
còn bundle đã ghim trong hồ sơ giữ `status: candidate` và `is_fixture: false`.
Giữ nguyên byte của bundle để checksum tiếp tục khớp biên bản.
[Định dạng bundle](https://github.com/ngnsusinn/anti-fake-news/blob/main/docs/model-bundle.md) ·
[Freeze AFN-049](https://github.com/ngnsusinn/anti-fake-news/issues/49)

**CLIP.** Dùng checkpoint OpenAI ở revision ghi trong
`configs/clip-reference.json`. Chuẩn bị cache trên máy có mạng, đặt
`HF_HOME` thành đường dẫn tuyệt đối và dùng lại cache đó khi chạy.
Khi chuyển cache, giữ cấu trúc thư mục `hub` và blob mà snapshot tham
chiếu. Sau khi chuyển, kiểm lại SHA-256 tại máy nhận.

```powershell
$env:HF_HOME = Join-Path (Get-Location).Path 'cache/huggingface'
$AfnClip = Get-Content configs/clip-reference.json -Raw | ConvertFrom-Json
$AfnSnapshot = & ./.venv/Scripts/hf.exe download $AfnClip.encoder.repo_id --revision $AfnClip.encoder.revision config.json preprocessor_config.json pytorch_model.bin
if ($LASTEXITCODE -ne 0) { throw 'Không tải được snapshot CLIP.' }
$AfnWeightsHash = (Get-FileHash (Join-Path $AfnSnapshot 'pytorch_model.bin') -Algorithm SHA256).Hash
if ($AfnWeightsHash -ne 'a63082132ba4f97a80bea76823f544493bffa8082296d62d71581a4feff1576f') {
    throw 'SHA-256 weights CLIP khác hash nguồn.'
}
```

Đối chiếu hash weights với SHA-256 do OpenAI/Hugging Face công bố ở
revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`. Loader còn đối chiếu
hash cấu hình processor với bundle.
[SHA-256 của weights](https://huggingface.co/openai/clip-vit-base-patch32/blob/3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268/pytorch_model.bin)

## 3. Khởi động loopback và kiểm health

Sao chép `.env.example` thành `.env` tại gốc gói. Giữ
`AFN_ENVIRONMENT=production`, `AFN_PREDICTOR_MODE=real` và
`AFN_HOST=127.0.0.1`. Điền SHA-256 của bundle được triển khai vào
`AFN_MODEL_METADATA_SHA256` và tạo `AFN_DEMO_TOKEN` trước khi đóng gói
Extension theo [hướng dẫn](extension-setup.md). Dùng cùng token và cổng
cho gói Extension và Backend. Có thể đặt biến môi trường thay cho sửa file.
Đặt `AFN_EXTENSION_ORIGIN=chrome-extension://<id>` theo ID của bản Extension
đã cài trong `chrome://extensions` để Backend cho phép request từ Extension.
Từ thư mục gốc đã giải nén:

```powershell
$env:HF_HUB_OFFLINE = '1'
Push-Location backend
try { & $AfnPython -m app } finally { Pop-Location }
```

Ở terminal còn lại chạy `curl.exe -i http://127.0.0.1:8000/health`.
Kỳ vọng HTTP 200, `contract_version: 0.2.0`, `model_ready: true`,
`X-AFN-Inference-Mode: real` và `X-AFN-Model-State: ready`. Nếu đổi
`AFN_PORT`, cập nhật URL tương ứng. Hành vi CORS qua Chromium được kiểm
ở AFN-038/044. [Hợp đồng API](https://github.com/ngnsusinn/anti-fake-news/blob/main/docs/api-contract.md)

Production dừng khởi động nếu thiếu token, bundle hoặc cache CLIP,
hay nếu bundle sai hash hoặc warm-up lỗi. Mặc định production yêu cầu
bundle `frozen`. Với bundle AFN-049 trong biên bản đã ký, đặt
`AFN_ALLOW_CANDIDATE_MODEL=true` và ghim SHA-256 của chính `metadata.json`
được ghi trong biên bản.

## 4. Smoke và khởi động lại offline

Từ thư mục `backend/` của checkout mã nguồn cùng commit với ZIP, chạy
kiểm tra HTTP production bằng `HF_HOME` và `HF_HUB_OFFLINE=1` đã đặt.
Script dùng UUID, PNG, nội dung tiếng Anh tổng hợp và token tạm.
Lấy `$AfnApprovedHash` từ biên bản AFN-049 và dùng đường dẫn bundle đã triển khai.

```powershell
& $AfnPython tests/smoke_local.py --bundle $AfnBundlePath --candidate --production --metadata-sha256 $AfnApprovedHash
```

Kỳ vọng health ready, 401 với request thiếu token, và 200 với
multipart hợp lệ. Smoke kiểm UUID, model ID/version, nhãn, score, thời
gian và truncation. Sau khi có wheelhouse, cache và bundle đã xác thực,
ngắt kết nối bên ngoài nhưng giữ loopback, chạy lại smoke ở một process
mới và ghi kết quả. Nếu thử trên máy đích riêng, ghi OS/CPU/Python và
mọi hạn chế trong checklist. [Checklist bàn giao](../release/backend-checklist.md)
