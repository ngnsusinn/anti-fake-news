# Kiểm tra phục hồi lỗi API — AFN-041

| Ca | Hành vi kiểm tra |
| --- | --- |
| HTTP 400, 401, 403, 413, 503 | Thông báo tiếng Việt theo lỗi, có bước xử lý cụ thể |
| Dịch vụ tắt, phản hồi không hợp lệ | Báo lỗi, không hiển thị thành công |
| Hết hạn phía client | Dừng chờ, ghi rõ Backend có thể vẫn xử lý |
| Thử lại | Giữ tiêu đề, thân bài và file; giữ nút thử lại khi sửa token hoặc nội dung; gửi UUID mới |

Chạy node --test tests/frontend/error-recovery.test.mjs. Browser smoke có ca
tiêm phản hồi 503 có kiểm soát, sau đó thử lại qua FastAPI mock thật. Đây là
ca kiểm tra UI và giao thức với dữ liệu tổng hợp. Phản hồi từ model thật được
kiểm tra trong đợt tích hợp #37/#45.
