# Kiểm thử Backend với bundle Multimodal thật

Đặt thư mục bundle do ML bàn giao tại `backend/artifacts/multimodal`. Chuẩn bị checkpoint CLIP đúng revision theo [hướng dẫn Backend](../../docs/backend-setup.md). Backend mặc định đọc cache từ `cache/huggingface` ở gốc repository hoặc từ `HF_HOME` trong môi trường tiến trình.

## Bundle ứng viên

Với bundle có `status: candidate` và `is_fixture: false`, chạy từ gốc repository:

```powershell
python backend/tests/smoke_local.py --candidate --bundle backend/artifacts/multimodal
```

Lệnh chạy model thật trên loopback ở chế độ `demo`, dùng một ảnh và bài viết tổng hợp để kiểm tra `GET /health`, xác thực token và `POST /predict`.

## Bundle production

Lấy bundle `status: frozen` và SHA-256 đã duyệt của `metadata.json` từ [AFN-049](https://github.com/ngnsusinn/anti-fake-news/issues/49). Từ gốc repository, thay giá trị ví dụ bằng digest được bàn giao:

```powershell
$AfnApprovedHash = '<sha256-tu-bien-ban-AFN-049>'
python backend/tests/smoke_local.py --bundle backend/artifacts/multimodal --metadata-sha256 $AfnApprovedHash
```

Để chạy dịch vụ production thường xuyên, điền digest vào `AFN_MODEL_METADATA_SHA256` trong `.env` và dùng `python -m app` từ thư mục `backend`. Git chỉ theo dõi hướng dẫn và schema trong thư mục artifact. Bundle, cache CLIP và token được lưu cục bộ.
