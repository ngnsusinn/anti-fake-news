# Môi trường ML và encoder CLIP — AFN-005 / AFN-006

Trạng thái: **đã chạy smoke trên macOS M1 và Windows x64**, đang chờ Backend review và xác nhận cấu hình máy demo. Mọi ảnh trong smoke là ảnh tổng hợp sinh
trong bộ nhớ; thời gian đo được chỉ dùng để lập kế hoạch, **không** phải kết quả
nghiên cứu hay chất lượng mô hình.

## 1. Cài đặt

Dùng chung một `.venv` với backend (bộ tiền xử lý và loader sau này nằm trong backend):

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt -r ml/requirements.txt
.venv/bin/python -m pip check
```

Windows dùng Python 3.13 cho môi trường chung đã kiểm tra; thay `.venv/bin/python` bằng `.\.venv\Scripts\python.exe`.
Linux: thêm `--extra-index-url https://download.pytorch.org/whl/cpu` để lấy torch bản CPU.

Cài thêm `ml/requirements.txt` không đổi phiên bản nào trong `backend/requirements.txt`
trên Windows x64/Python 3.13.0. Hai bộ pin cài chung và `pip check` đạt.

## 2. Encoder được ghim (`configs/clip-reference.json`)

| Mục | Giá trị |
| --- | --- |
| Checkpoint | `openai/clip-vit-base-patch32` |
| Revision | `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` |
| File tải | `config.json`, `preprocessor_config.json`, `pytorch_model.bin` (~577 MB) |
| Lớp mô hình / processor | `transformers.CLIPModel` / `transformers.CLIPImageProcessor` |
| Đặc trưng | `get_image_features(...).pooler_output` (đã qua visual projection) |
| Số chiều đo thực tế | **512** (= `model.config.projection_dim`) |
| dtype | `float32` (tham số và embedding) |
| Chuẩn hóa | L2 theo hàng qua `app.preprocessing.l2_normalize_embeddings` |
| Chế độ | `eval()`, `requires_grad_(False)`, `torch.inference_mode()`; **không fine-tune** |

Revision không có `model.safetensors`, nên dùng `pytorch_model.bin`; transformers 5 nạp
ở chế độ an toàn (`weights_only`). Chỉ tải 3 file trên, bỏ bản Flax/TF.

**Ghi chú dùng weights:** weights CLIP của OpenAI được công bố cho mục đích nghiên cứu;
model card nêu việc triển khai thực tế nằm ngoài phạm vi nếu chưa đánh giá trong miền.
Dự án chỉ dùng encoder đóng băng, chạy cục bộ, cho demo môn học. Weights/cache
**không commit** (`.gitignore` đã chặn `cache/`, `weights/`, `checkpoints/`, `*.pt`, `*.safetensors`…).

## 3. Chuỗi tiền xử lý dùng chung (AFN-005)

Một module duy nhất `backend/app/preprocessing.py` (`PREPROCESS_VERSION = afn-preprocess-v1`)
cho cả train offline lẫn inference online:

**Văn bản** — `preprocess_text(title, body) -> TextPreprocessResult`
1. NFKC; bỏ ký tự vô hình (soft hyphen, zero-width, BOM).
2. Đưa mọi biến thể gạch nối/gạch ngang về `-`; nối lại từ bị ngắt dòng `infor-\nmation`.
3. Xóa URL (`http(s)://`, `ftp://`, `www.`).
4. Gộp mọi khoảng trắng thành một dấu cách, trim. Giữ nguyên hoa/thường (TF-IDF tự lowercase).
5. Cắt thân bài còn **1.500 từ** (từ = token tách bởi khoảng trắng), `truncated=True` nếu bị cắt.
   Tiêu đề không tính vào 1.500 từ (đã bị giới hạn 500 ký tự ở API) — *đề xuất, chờ AFN-004 xác nhận*.
6. Ghép `title + "\n" + body`; tiêu đề rỗng thì chỉ dùng body.
7. Body rỗng sau chuẩn hóa → `EmptyTextError` (con của `PreprocessingError`, Backend map 400).

Giới hạn 50.000 ký tự là giới hạn **vận chuyển** của Backend (kiểm tra trước); 1.500 từ là
giới hạn **nội dung** của ML. Fixture `api_max_chars_not_word_cap` chứng minh văn bản hợp lệ
ở API vẫn bị ML cắt.

**Ảnh** — `load_image_rgb(bytes) -> PIL.Image (RGB, 8-bit)`
- Nhận diện định dạng theo nội dung, chỉ JPEG/PNG; kiểm tra ≤ 20.000.000 pixel từ header trước khi decode.
- Áp hướng EXIF (`ImageOps.exif_transpose`) rồi bỏ EXIF.
- Alpha (RGBA/LA/palette trong suốt) ghép lên nền trắng cố định; PNG 16-bit quy về 8-bit.
- Lỗi decode → `InvalidImageError` (400). Resize/crop/mean-std do `CLIPImageProcessor` đã ghim làm.

**Embedding** — `l2_normalize_embeddings(x, expected_dim=None)`
- Trả float32, chuẩn hóa L2 theo hàng; NaN/Inf/chuẩn 0 → `NonFiniteEmbeddingError`.
- Lỗi này **không** phải lỗi đầu vào: Backend phải coi là lỗi mô hình (503), không phải 400.

Đổi bất kỳ quy tắc nào → tăng `PREPROCESS_VERSION`, trích lại embedding, báo Backend/DATA.

## 4. Smoke test và kết quả đo

```sh
.venv/bin/python scripts/smoke_clip.py                       # tải (nếu cần) + kiểm tra
.venv/bin/python scripts/smoke_clip.py --offline             # chỉ dùng cache, không mạng
.venv/bin/python scripts/smoke_clip.py --report cache/smoke/report.json
```

Cache mặc định `<repo>/cache/huggingface/hub`, hoặc `$HF_HOME/hub` nếu đặt `HF_HOME`.
Exit code 0 chỉ khi toàn bộ 16 check pass (revision, file, eval, frozen, dtype, EXIF,
dim, hữu hạn, norm, shape, tất định, batch = đơn lẻ, ảnh khác → embedding khác, weights không đổi).

Kết quả ngày 2026-11-23 (4 ảnh tổng hợp, 20 lượt đo, CPU, 4 luồng torch):

| Máy | Python | torch / transformers | Tải lần đầu | Nạp model+processor | Batch đầu (4 ảnh) | 1 ảnh (trung vị / max) |
| --- | --- | --- | --- | --- | --- | --- |
| Apple M1, 8 nhân, 16 GB RAM, không CUDA (có MPS nhưng không dùng) | 3.14.7 | 2.15.0 / 5.24.0 | 17,3 s | 0,23 s (online) / 0,18 s (offline) | 0,74 s | 43,6 / 60,6 ms |

Chạy lại `--offline` pass toàn bộ → cache cục bộ dùng được không cần mạng.
`param_count = 151.277.313` (cả nhánh text của CLIP được nạp nhưng chỉ dùng nhánh ảnh).

Kiểm tra độc lập trên Windows x64, Python 3.13.0, CPU với 6 luồng Torch:
16/16 kiểm tra CLIP đạt ở hai chế độ online và offline, embedding 512 chiều.
Đây là bằng chứng tương thích của môi trường chung. Xác nhận lại khi máy demo
dùng cấu hình khác.

**Phương án CPU trước khi mở rộng batch:** ~44 ms/ảnh ⇒ 400 ảnh ≈ 20–30 s trên CPU M1,
nên trích embedding cho dataset 200–500 mẫu chạy CPU là đủ; chưa cần GPU/MPS.
Các số đo encoder hỗ trợ ước lượng thời gian trích đặc trưng. Ca đo độ trễ end-to-end dưới 10 giây dùng mô hình đầy đủ trên máy demo.

## 5. Bàn giao cho Backend loader (#24/#37)

- Checkpoint/processor/revision/dim/dtype: đọc từ `configs/clip-reference.json`, đừng ghi cứng.
- Nạp một lần khi khởi động, `eval()` + `requires_grad_(False)`, gọi trong `torch.inference_mode()`.
- Thứ tự: `load_image_rgb` → `CLIPImageProcessor` → `get_image_features().pooler_output`
  → `l2_normalize_embeddings(expected_dim=512)`.
- Văn bản: `preprocess_text(title, text)`; `result.truncated` → `PredictionResult.text_truncated`.
- Map lỗi: `PreprocessingError` → 400 `invalid_input`; `NonFiniteEmbeddingError`/lỗi model → 503.
- Đặt `HF_HUB_OFFLINE=1` ở demo để không bao giờ gọi mạng lúc chạy.

## 6. Việc còn mở

| Việc | Owner | Ghi chú |
| --- | --- | --- |
| Xác nhận môi trường demo | ML + Backend | Dùng Python 3.13 làm mốc đã kiểm tra môi trường chung. Đối chiếu máy demo nếu cấu hình khác. |
| Xác nhận quy tắc 1.500 từ chỉ tính body, ghép `title\n body` | INTEGRATION (#4) | Điều kiện Done của #5 |
| Backend #23 dùng lại `load_image_rgb` thay vì tự decode | BACKEND | Tránh hai bản tiền xử lý lệch nhau |
| Fixture parity dữ liệu thật (manifest) | DATA (#16) | Fixture hiện tại là tổng hợp |
| Chốt giao thức trước freeze | Integration + ML | [AFN-004](experiment-protocol.md) bám theo phiếu đề tài: bài viết tiếng Anh, UI tiếng Việt. |
