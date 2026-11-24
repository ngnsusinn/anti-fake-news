# Kịch bản demo Extension — AFN-057

Dùng trang và ảnh tổng hợp tại `tests/fixtures/pages/article.html` và
`tests/fixtures/pages/synthetic.png` để kiểm tra kỹ thuật. Chúng nằm ngoài tập
Test nghiên cứu. Với demo mô hình, thay bằng bài tiếng Anh và ảnh được phép
dùng ngoài Test, lưu bằng chứng nguồn theo quy trình dữ liệu.

1. Cài gói theo [hướng dẫn](extension-setup.md). Để phục vụ fixture cục bộ, chạy
   `python -m http.server 8765 --bind 127.0.0.1 --directory tests/fixtures/pages`.
   Mở `http://127.0.0.1:8765/article.html` rồi bấm biểu tượng Extension.
2. Kiểm tra đúng URL tab, sửa/dán thân bài tiếng Anh, chọn một ảnh ứng viên.
   Khi tải ảnh trang thất bại, chọn `synthetic.png` từ máy và nhìn preview.
3. Nhập địa chỉ Backend, token khi được yêu cầu, rồi bấm **Phân tích**.
   Ghi nhận nhãn, điểm fake_score, tên và phiên bản model, thời gian, trạng thái
   cắt văn bản và cảnh báo giới hạn. Kết quả mock được hiển thị riêng cho dev/test.
4. Sửa một đoạn trong thân bài. Kết quả của bản cũ được ẩn; bấm **Phân tích**
   để gửi bản vừa sửa với UUID mới.
5. Dừng Backend trong buổi thử cục bộ, bấm **Phân tích**, kiểm tra thông báo
   và dữ liệu còn nguyên. Khởi động lại rồi bấm **Thử lại**. Lưu bằng chứng
   giữ tiêu đề, thân bài và file cùng trạng thái mới.

Rehearsal cuối cần gói Backend #54, nghiệm thu UX #55 và hồi quy #56 với
artifact đã khóa. Ghi tên người chạy độc lập, phiên bản gói/model và kết quả
từng bước trong buổi rehearsal trước bàn giao.
