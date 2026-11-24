# Cài Extension unpacked — AFN-057

## Đóng gói và cài đặt

1. Từ gốc repo, chạy `python scripts/package_extension.py`. Gói được tạo ở
   `release/extension`. Sau khi cập nhật mã, có thể dùng
   `python scripts/package_extension.py --output release/extension-next`.
2. Mở `chrome://extensions`, bật **Developer mode**, chọn **Load unpacked**,
   rồi chọn thư mục đã tạo. Ghi lại ID hiển thị bên dưới tiện ích.
3. Origin của gói là `chrome-extension://<ID>`. Dùng giá trị này cho
   `AFN_EXTENSION_ORIGIN` trong cấu hình Backend khi hỗ trợ CORS của #38 đã có.
   Khởi động Backend tại `127.0.0.1` và nhập đúng cổng trong trang phân tích.
4. Dùng **Kiểm tra kết nối** để kiểm tra /health. Chỉ demo suy luận thật khi
   Backend chạy mode real, đã nạp artifact đã khóa và trả `model_ready=true`.

Gói chỉ lấy mã MV3 và tệp giao diện trong danh sách runtime của script đóng gói. Token demo nhập trong tab, được cấp
riêng từ cấu hình Backend. Xem [kết nối API](extension-config.md) và
[kịch bản demo](demo-script.md). Phát hành theo mô hình unpacked của dự án.

## Kiểm tra trên máy khác

Sau khi cài dependencies Backend và Playwright theo
[hướng dẫn Chromium](extension-w1.md), có thể kiểm tra gói vừa đóng:

```powershell
$env:AFN_EXTENSION_UNPACKED = (Resolve-Path release/extension).Path
python scripts/test_extension_smoke.py
```

Lệnh trên kiểm tra Chromium, FastAPI mock và luồng real-mode 503 với token
thử nghiệm do runner tạo. Rehearsal
với mô hình đã khóa dùng gói Backend #54 và lệnh ở
[biên bản hồi quy](../reports/extension-final-check.md).
