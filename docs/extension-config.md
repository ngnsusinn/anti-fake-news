# Kết nối Extension với Backend cục bộ — AFN-027

Trang phân tích có địa chỉ dịch vụ, token demo và thời gian chờ. Dùng
http://127.0.0.1:8000 hoặc đổi cổng theo Backend. Token nằm trong trường mật khẩu
của tab và được gửi bằng X-Demo-Token khi bấm **Phân tích**. Nút **Kiểm tra kết nối**
dùng GET /health và không gửi token. Thời gian chờ mặc định là 30 giây.

Mở hình ảnh hoặc tải tệp JPEG/PNG, nhập phần thân bài rồi bấm **Phân tích**. Trang
tạo UUID và gửi multipart để trình duyệt tự đặt boundary. Service worker không
gửi request. Tab giữ tệp trong bộ nhớ để thử lại.

Để phát triển nội bộ, xem [cách bật mock](dev-mock.md). Backend mock được đánh dấu
trên giao diện. Từ hợp đồng v0.2.0, cả chế độ mock và real đều yêu cầu nhập token
trùng với `AFN_DEMO_TOKEN` của Backend. Token thiếu hoặc sai trả 401. Chế độ real
trả 503 nếu token và dữ liệu hợp lệ nhưng model chưa sẵn sàng. Bàn giao model thật
theo #37/#38; giao diện kết quả
ở module result-view chỉ nhận dữ liệu đã qua kiểm tra request. Bàn giao nội dung và review UI cuối ở #40. Hợp đồng và form-state tiếp tục được đối chiếu ở #8/#12.
