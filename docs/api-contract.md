# Hợp đồng API v0.2.0 — AFN-022 / AFN-023

Trạng thái: triển khai local, **chưa có phê duyệt ML/Extension**. Base URL:
`http://127.0.0.1:8000`. Giữ nguyên tên trường JSON/chữ ký Predictor; thay đổi hành vi
so với v0.1.1: token và validation bắt buộc trong cả real/mock, trước model readiness.
Fixture hiện tại: `backend/tests/fixtures/api/v0.2.0/`; v0.1.1 được giữ làm lịch sử.

## GET /health

Không yêu cầu token. HTTP 200 chỉ chứng minh dịch vụ phản hồi:

```json
{"service_status":"ok","model_ready":false,"contract_version":"0.2.0"}
```

Health/predict/lỗi có các header `X-AFN-Inference-Mode: real|mock`,
`X-AFN-Model-State: not_loaded|ready|error`, `Cache-Control: no-store`.
Real chưa có loader, mặc định not_loaded/false. Mock ready chỉ là mock sẵn sàng.
Không trả token, đường dẫn artifact hay thông điệp ngoại lệ nội bộ.

## POST /predict

Yêu cầu đúng một header `X-Demo-Token` khớp `AFN_DEMO_TOKEN` qua so sánh
`hmac.compare_digest`. Thiếu/sai/trùng token hoặc server chưa cấu hình secret: **401**,
kể cả mock, trước khi đọc body. Chưa có chính sách 403; `forbidden` vẫn giữ trong schema.

Chỉ nhận multipart/form-data; một file, tối đa ba trường text. Từ chối trường lạ/trùng,
thiếu boundary hoặc phần kết thúc multipart. Không nhận JSON hay URL ảnh.

| Part | Bắt buộc | Ràng buộc |
| --- | --- | --- |
| request_id | Có | UUID client tạo, phản hồi canonical khi parse an toàn |
| title | Không | <=500 Unicode code points; giữ nguyên; thiếu là null, cho phép rỗng |
| text | Có | <=50.000 code points trước trim; không rỗng sau trim |
| image | Có | JPEG/PNG; <=10.485.760 bytes (10 MiB); <=20.000.000 pixels |

Độ dài chuỗi dùng Python code points, không phải byte UTF-8 hay UTF-16; JS có thể dùng
`Array.from(text).length`. Parser giới hạn mỗi part text 200.000 bytes.
Phạm vi bài báo tiếng Anh chờ ML/Extension xác nhận. Backend không nhận diện ngôn ngữ,
nối title/body hay áp dụng mức cắt ML 1.500 từ; `text_truncated` do Predictor cung cấp.

Toàn body có trần `AFN_MAX_REQUEST_BYTES`, mặc định **12.582.912 bytes (12 MiB)**,
đã thực thi, giá trị mặc định còn chờ consumer review. Giới hạn ảnh tách biệt với text,
boundary, header từng part và epilogue. Ảnh đúng 10 MiB + text tối đa + overhead thông thường
được chấp nhận với mặc định. Đúng trần được phép, thêm một byte bị từ chối.

Content-Length chỉ giúp từ chối sớm; luôn đếm byte thực nhận qua ASGI, kể cả thiếu hoặc
khai nhỏ Content-Length. Header độ dài sai/trùng hoặc Content-Encoding khác identity: 400.
Trần tính HTTP body, không tính HTTP request headers (do server kiểm soát).
Parser dừng trước khi ghi chunk file vượt 10 MiB vào spool. Đóng mọi tệp tạm khi thành công,
lỗi parse/decode, vượt trần, multipart chưa hoàn tất hoặc client ngắt kết nối.
Lỗi đầu vào phát hiện sớm có thể trả 400 mà không đọc hết body để tìm lỗi vượt trần sau đó.

MIME phải chính xác `image/jpeg` hoặc `image/png`, khớp format thực do Pillow phát hiện;
tên file không quyết định format. Kiểm tra pixel trước decode, verify/decode đầy đủ,
từ chối ảnh hỏng/decompression bomb. Gọi nguyên bản helper ML cho EXIF/RGB/alpha nền trắng,
grayscale/palette/16-bit; không resize/normalize CLIP. Đóng RGB sau validation,
giữ bytes mã hóa gốc cho Predictor, không recompress. Xem [giao diện](inference-interface.md).

## Thứ tự, lỗi và correlation

Token → header/giới hạn byte trong lúc parse → form fields → ảnh → readiness → Predictor.
Không decode/gọi Predictor khi token sai. Real chưa ready vẫn phải validation.
Không dùng binding Form/File tự động; lỗi đầu vào thuộc hợp đồng trả 400, không phải 422.
Chỉ bắt lỗi đầu vào dự kiến, không chuyển lỗi lập trình thành invalid_input.

| HTTP | error_code | Nguyên nhân |
| --- | --- | --- |
| 400 | invalid_input | UUID/text/title/multipart/file/MIME/decode/pixel không hợp lệ |
| 401 | invalid_token | Token thiếu/sai/trùng hoặc server chưa cấu hình |
| 413 | request_too_large | Vượt trần byte file hoặc toàn body |
| 503 | model_not_ready | Đầu vào hợp lệ nhưng model chưa sẵn sàng/provider lỗi |

```json
{"detail":"Invalid input","error_code":"invalid_input","request_id":null}
```

Chỉ echo UUID không nhập nhằng đã parse an toàn. ID thiếu/sai/trùng hoặc lỗi trước parse đầy đủ
(auth/byte/parser) dùng null; không tạo ID thay thế. 503 sau validation echo UUID.
Không echo bài báo, ảnh, tên file, token, đường dẫn hoặc lỗi parser/Pydantic/Pillow.
Client giữ ID gốc để đối chiếu lỗi sớm và bỏ phản hồi của yêu cầu đã hết hiệu lực.

## Kết quả

HTTP 200 hiện chỉ có trong mock opt-in dev/test. `PredictResponse` chứa:
UUID request_id; label fake/real; fake_score float hữu hạn [0,1]; model_version/model_id
là chuỗi không trắng; processing_time_ms số nguyên >=0; text_truncated boolean; không trường thừa.
Điểm số không mặc nhiên là xác suất calibrated; Backend không tự chọn ngưỡng nhãn/metadata.
Thời gian monotonic quanh lời gọi Predictor, loại trừ upload và validation ảnh tại transport.
Mock giữ model_id `dev-mock-not-a-model`, model_version `mock-v0.1.1`; dữ liệu cố định không
phải dự đoán thật/accuracy. Real vẫn trả 503 với đầu vào hợp lệ; loader/warm-up thuộc #37/#38.

## Ví dụ client

PowerShell, token cung cấp cục bộ và example.png phải hợp lệ:

```powershell
curl.exe -i http://127.0.0.1:8000/predict `
  --header "X-Demo-Token: $env:AFN_DEMO_TOKEN" `
  --form-string "request_id=550e8400-e29b-41d4-a716-446655440000" `
  --form-string "text=Synthetic English article for local testing." `
  --form "image=@./example.png;type=image/png"
```

Extension analyze.js dùng FormData; không tự đặt Content-Type vì trình duyệt sinh boundary:

```javascript
const requestId = crypto.randomUUID();
const form = new FormData();
form.append("request_id", requestId);
if (title != null) form.append("title", title);
form.append("text", text);
form.append("image", imageFile);
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), timeoutMs);
try {
  const response = await fetch("http://127.0.0.1:8000/predict", {
    method: "POST", headers: { "X-Demo-Token": demoToken },
    body: form, signal: controller.signal
  });
  const payload = await response.json();
  // Check status, local requestId and inference mode before displaying payload.
} finally {
  clearTimeout(timer);
}
```

Timeout do client cấu hình, chờ Extension review; mục tiêu 10 giây không phải timeout bắt buộc.
Abort phía client không đảm bảo hủy compute phía server. CORS/browser integration thuộc #38;
chưa chứng minh ví dụ cross-origin chạy được. Chỉ phục vụ loopback; không ghi secret vào URL/log/repo.
CORS không thay auth. Các khác biệt tài liệu nền và review còn thiếu ghi trong
[báo cáo](implementation-issues-22-23.md).
