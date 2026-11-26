# Cài Extension unpacked — AFN-057

## Đóng gói và cài đặt

1. Sau khi cấu hình Backend và cài các phụ thuộc Python của Backend, chạy
   `python scripts/package_extension.py` từ gốc repo. Script đọc `AFN_DEMO_TOKEN`
   và `AFN_PORT` từ môi trường hoặc `.env` rồi tạo gói ở `release/extension`.
   Sau khi cập nhật mã hoặc đổi token, có thể dùng
   `python scripts/package_extension.py --output release/extension-next`.
2. Mở `chrome://extensions`, bật **Developer mode**, chọn **Load unpacked**,
   rồi chọn thư mục đã tạo. Ghi lại ID hiển thị bên dưới tiện ích.
3. Origin của gói là `chrome-extension://<ID>`. Đặt đúng giá trị này cho
   `AFN_EXTENSION_ORIGIN` để Backend cấp quyền CORS cho origin đó. Khởi động
   hoặc khởi động lại Backend tại `127.0.0.1`.
4. Mở bài viết có ảnh JPEG/PNG, bấm biểu tượng **Anti Fake News** rồi bấm
   **Phân tích** để xem điểm `fake_score` theo phần trăm và nhãn **Fake** hoặc **Real**.
   Chọn **Xem chi tiết** để xem văn bản và ảnh đã gửi, quy trình xử lý và thông số lượt dự đoán.
   Popup dùng ảnh JPEG/PNG hợp lệ đầu tiên tải được và nhắc đổi bài nếu
   thiếu nội dung hoặc ảnh. Với demo suy luận thật, kiểm `/health` có mode
   real và `model_ready=true`, rồi đối chiếu model version trong chi tiết
   với phiên bản bundle dùng cho buổi demo.

Gói unpacked chứa token dùng với Backend cục bộ. Giữ gói trên máy đã cấu hình.
Xem [kết nối API](extension-config.md) và
[kịch bản demo](demo-script.md). Phát hành theo mô hình unpacked của dự án.

## Tiện ích đã được nạp từ thư mục mã nguồn

Nếu Chrome đang nạp trực tiếp thư mục `extension/`, chạy
`python scripts/package_extension.py --configure-source` từ gốc repo. Script ghi
cấu hình cục bộ vào đúng thư mục đang nạp. Mở lại popup để phân tích. Chạy lại
lệnh khi đổi token hoặc cổng Backend.

## Kiểm tra trên máy khác

Sau khi cài dependencies Backend và Playwright theo
[hướng dẫn Chromium](extension-w1.md), chạy kiểm thử trên gói tạm:

```powershell
python scripts/test_extension_smoke.py
```

Lệnh trên kiểm tra Chromium, FastAPI mock và luồng real-mode 503 với token
thử nghiệm do runner tạo. Rehearsal
với mô hình đã khóa dùng gói Backend #54 và lệnh ở
[biên bản hồi quy](../reports/extension-final-check.md).
