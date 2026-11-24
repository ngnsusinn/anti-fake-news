# Rà giao diện tiếng Việt — AFN-055

- Tiêu đề được ghi rõ là tùy chọn. Thân bài có hướng dẫn giới hạn, focus bàn
  phím và trạng thái lỗi nối với trường nhập.
- Preview ảnh, nhãn upload và nút Phân tích/Thử lại dùng được ở viewport hẹp.
  Chỉnh sửa bản nháp không tự gửi, lỗi API giữ dữ liệu trong tab.
- Trên bản tích hợp dev/test, cảnh báo mock, tên/phiên bản model, trạng thái
  cắt văn bản và giải thích fake_score hiển thị cạnh kết quả. Nút Thử lại\n  tham chiếu thông báo trạng thái để trình đọc màn hình đọc được ngữ cảnh.

Browser smoke kiểm thứ tự focus, viewport 360 px và các luồng dữ liệu. Mock
chứng minh UI và hợp đồng; nghiệm thu nội dung kết quả thật và bố cục cuối
cần phần result-view #40 và máy demo cùng bản build đã khóa.
