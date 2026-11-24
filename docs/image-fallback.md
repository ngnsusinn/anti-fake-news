# Chọn ảnh và nhập thủ công — AFN-025

Chọn một ứng viên từ trang hoặc tải một tệp JPEG/PNG từ máy. Tiện ích thử lấy
bytes của ứng viên bằng quyền trình duyệt hiện có. Khi máy chủ chặn yêu cầu, ảnh
hỏng hoặc vượt giới hạn, hãy chọn ảnh khác hay tải tệp thủ công. Ảnh loopback chỉ được tải khi cùng origin với tab nguồn. Địa chỉ Backend cấu hình riêng, phục vụ kết nối API.

Tiện ích kiểm tra 10 MiB và 20.000.000 pixel trước khi giải mã. Backend xác thực
lại khi nhận request. Preview được giải phóng khi đổi ảnh, bỏ ảnh hoặc rời trang.
Tệp nằm trong bộ nhớ trang để có thể thử lại; khi đóng hoặc tải lại trang, chọn
lại ảnh.

Bàn giao cho #26/#27: module form-state cung cấp get/set/subscribe; bộ chọn chuyển tệp vào state của tab và multipart chỉ gửi bytes. Đối chiếu các quyết định hợp đồng ở #8 và review bàn giao ở #12 trước nghiệm thu.
