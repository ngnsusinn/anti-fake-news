# Kịch bản demo Extension — AFN-057

Dùng trang và ảnh tổng hợp tại `tests/fixtures/pages/article.html` và
`tests/fixtures/pages/synthetic.png` để kiểm tra kỹ thuật. Chúng nằm ngoài tập
Test nghiên cứu. Với demo mô hình, thay bằng bài tiếng Anh và ảnh được phép
dùng ngoài Test, lưu bằng chứng nguồn theo quy trình dữ liệu.

1. Cài gói theo [hướng dẫn](extension-setup.md). Để phục vụ fixture cục bộ, chạy
   `python -m http.server 8765 --bind 127.0.0.1 --directory tests/fixtures/pages`.
   Mở `http://127.0.0.1:8765/article.html` rồi bấm biểu tượng Extension.
2. Bấm **Phân tích**. Popup tự trích văn bản và dùng ảnh JPEG/PNG hợp lệ
   đầu tiên tải được. Ghi nhận nhãn **Fake** hoặc **Real** và điểm
   `fake_score` theo phần trăm. Mở **Xem chi tiết** để đối chiếu đầu vào,
   phiên bản mô hình và thời gian xử lý. Mock hiện dòng **Kết quả giả lập**.
3. Mở một bài khác rồi lặp lại để kiểm tra tiện ích lấy nội dung từ tab hiện tại.
4. Dừng Backend, bấm **Phân tích** và kiểm tra thông báo kết nối. Khởi động lại
   Backend rồi bấm **Phân tích** lần nữa.

Rehearsal cuối cần gói Backend #54, nghiệm thu UX #55 và hồi quy #56 với
artifact đã khóa. Ghi tên người chạy độc lập, phiên bản gói/model và kết quả
từng bước trong buổi rehearsal trước bàn giao.
