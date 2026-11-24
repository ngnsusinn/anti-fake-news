# Giao diện Predictor v0.2.0

#22/#23 giữ nguyên chữ ký Python và JSON của #7/#8/#9. Hành vi transport đổi theo
[API contract](api-contract.md); **ML/Extension chưa phê duyệt**.

```python
class PredictorInput(PredictFormFields):
    image_bytes: bytes

class Predictor(Protocol):
    def predict(self, inputs: PredictorInput) -> PredictionResult: ...
```

PredictFormFields: UUID, title tùy chọn <=500 code points, text <=50.000 trước trim,
không rỗng sau trim. Transport xác thực token/multipart/ảnh trước khi tạo PredictorInput.
image_bytes là JPEG/PNG mã hóa gốc đã kiểm tra MIME/format, <=10 MiB, <=20.000.000 pixels.
Schema bytes riêng lẻ không xác thực ảnh; caller Python ngoài HTTP phải tự dùng validator.
Không dùng request_id/tên file/nguồn bài làm đặc trưng ML.

## Tiền xử lý ảnh dùng chung

backend/app/preprocessing.py lấy **nguyên bản** từ PR #68, commit
`9b5a0ab1b0ce19cf04467e845a8772713f858da8`, blob
`c235ab427f0ecb8f3d6f9c2a0b0908c5712f718d` của repository này.
PREPROCESS_VERSION là afn-preprocess-v1; không sửa thuật toán ML-owned.
Pillow 13.0.0, NumPy 2.5.5 khớp manifest ML tại commit đó.
Backend kiểm tra trên Windows/Python 3.13.1; chưa xác nhận toàn bộ môi trường ML.

image_validation.validated_image kiểm tra bytes/MIME/format/pixel/verify rồi gọi
preprocessing.load_image_rgb: EXIF orientation, RGB 8-bit, alpha nền trắng,
palette/grayscale/16-bit theo helper. Context manager đóng RGB khi thoát.
validate_image_bytes dùng context này và đóng kết quả ngay, giữ bytes gốc qua seam.
Không có quy tắc EXIF/RGB thứ hai, không resize/normalize CLIP, không recompress JPEG.
Provider thật #37 sẽ dùng cùng helper để tạo RGB; decode lại là chi phí giữ seam hiện hữu.
Đổi seam sang RGB cần review/version mới.

Các hàm text/embedding đi kèm module upstream giữ nguyên nhưng transport không gọi.
Quy tắc 1.500 từ/title/body và protocol #4 còn chờ review; không tự áp dụng tại Backend.
ML chịu trách nhiệm tokenizer, CLIP resize/normalize, TF-IDF, sparse hstack,
Logistic Regression, threshold/metadata và text_truncated. Không fit/retrain trong request.

## Kết quả và vòng đời

PredictionResult: label fake/real, fake_score hữu hạn [0,1], model_version/model_id
không trắng, text_truncated boolean; không có trường thừa. Backend thêm UUID và thời gian
monotonic quanh lời gọi synchronous Predictor trong thread pool. Không tự tạo model metadata
hay đổi ngưỡng. Điểm số không mặc nhiên là xác suất calibrated.

Adapter quản lý not_loaded/ready/error; get_predictor là DI seam. initialize(factory)
là điểm nối Python; factory thật cần kiểm tra artifact/warm-up trước ready.
Không nạp mô hình khi import hoặc khi thấy artifact path tồn tại. Lỗi provider/đầu ra sai schema
thành 503 đã làm sạch và adapter error; không fallback mock. Shutdown đóng provider/xóa tham chiếu.
Recovery cần initialize/restart tường minh.

Real HTTP vẫn bị chặn 503 sau validation, kể cả dependency override; loader thuộc #37.
Mock chỉ khi đồng thời environment dev/test và predictor_mode mock; vẫn cần token/ảnh hợp lệ.
Mock không dùng nội dung để suy luận. Health ready trong mock chỉ có nghĩa mock sẵn sàng.

## Review cần thiết

ML: parity helper, dependency pins, bytes/RGB seam, tương thích môi trường.
Extension: token, lỗi 400/401/413/503, correlation, fixture v0.2.0.
Backend/repo owner: default body cap 12 MiB và tích hợp.
Chưa có phê duyệt hoặc yêu cầu review bên ngoài mới trong lần này. Nguồn upstream có báo cáo merge,
nhưng handoff/protocol #4 còn pending; không coi issue closed là bằng chứng chấp thuận.
Xem [báo cáo](implementation-issues-22-23.md).
