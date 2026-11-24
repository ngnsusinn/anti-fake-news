# Hồi quy Extension — AFN-056

| Ca | Môi trường và tiêu chí |
| --- | --- |
| Phiên, DOM và nhiều tab | Chromium, fixture trang tĩnh/động, phiên không lẫn dữ liệu |
| Ảnh trang và upload thủ công | Đọc bytes của ảnh hợp lệ; dùng upload khi ảnh nguồn lỗi |
| Validation, health chưa ready, lỗi 503/401 và retry | FastAPI mock và phản hồi có kiểm soát; làm lại với cùng tệp sau khi đổi token |
| Sai UUID và phản hồi đến muộn | Fixture HTTP có kiểm soát; chỉ lượt hiện tại được hiển thị |
| Tải lại trang phân tích | DTO nguồn được đọc lại, ảnh trong bộ nhớ được chọn lại |
| Backend real chưa nạp model | FastAPI chạy chế độ mặc định, trả 503 và giữ bản nhập |

Chạy từ gốc repo với Python có bộ pin Backend và Node có Playwright:
python scripts/test_extension_smoke.py. Lệnh khởi động hai service loopback riêng
và tắt chúng sau kiểm thử. Có thể đặt AFN_PLAYWRIGHT_PATH theo docs/extension-w1.md.

## Nghiệm thu model thật

Cần #37/#38 và artifact/model đã khóa ở #49 để chạy qua predictor thật. Chạy
python scripts/test_extension_smoke.py --real-endpoint http://127.0.0.1:8000.
Truyền token cục bộ của Backend qua biến môi trường AFN_REAL_TEST_TOKEN.
Lệnh yêu cầu health báo mode real và model_ready=true. Dùng fixture tổng hợp
để kiểm tra luồng giao diện, không đo chất lượng nghiên cứu. Ghi phiên bản
backend/model và bằng chứng UI ở checkpoint #45/#49 trước khi nghiệm thu.
