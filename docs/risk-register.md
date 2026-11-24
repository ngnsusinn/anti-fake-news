# Sổ theo dõi rủi ro — AFN-015

Cập nhật ngày 23/11/2026. “Chưa có bằng chứng” nghĩa là **chưa xác minh được trên nhánh mặc định và các issue tại thời điểm kiểm tra**, không khẳng định thành viên chưa làm ở máy/nhánh khác. Hạn xử lý phải được nhóm xác nhận.

| Mã | Rủi ro / khoảng trống đã nhận diện | Mức độ | Người gỡ / issue | Hướng xử lý | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| R01 | [PR #66](https://github.com/ngnsusinn/anti-fake-news/pull/66) có pilot **165/400** đủ bài+ảnh; [PR #67](https://github.com/ngnsusinn/anti-fake-news/pull/67) báo **400 mẫu thu hồi, 286 ứng viên cả body+ảnh**, nhưng chưa QA kiểm tra manifest/checksum và quyền nguồn | Cao | DATA `locnguyen230`, #2/#3 | Bàn giao manifest bất biến, SHA256SUMS, quyền nguồn, audit đúng bài/ảnh và chứng minh resume | Số lượng được báo cáo; nghiệm thu còn chặn |
| R02 | Batch ghi 396 khóa tiêu đề sự kiện phân biệt nhưng chưa gán `event_id` cho cả 400 mẫu, không tương đương số nhóm độc lập đã kiểm chứng; chưa chia 70/15/15 | Cao | DATA `locnguyen230`, #3/#18 | Gán/duyệt group key, cung cấp split checksum, kiểm tra leakage trước Train/Test | Chặn nghiệm thu |
| R03 | Chưa thấy cấu hình/chính sách chọn mô hình đã duyệt trên nhánh mặc định | Cao | INTEGRATION `fulord26`, #4 | Chốt seed 42, C/ngưỡng bằng Validation, cấm xem Test trước khóa | Đang mở |
| R04 | [PR #68](https://github.com/ngnsusinn/anti-fake-news/pull/68) có **16/16 online + 16/16 offline** trên Windows x64, embedding 512 chiều, trung vị 118,4/84,8 ms mỗi ảnh tổng hợp; còn chờ review và xác nhận máy demo/Python | Trung bình | ML `0xDa1Vu` + BACKEND `Phuc1232`, #6 | BACKEND review, chốt Python và đo lại đúng máy demo nếu khác | Smoke đã báo cáo, chưa nghiệm thu |
| R05 | API/Predictor v0.1.1 còn nháp; chưa chốt ngôn ngữ, EXIF, size, timeout | Cao | BACKEND `Phuc1232` cùng ML/EXTENSION, #8 | Review liên vai trò; cập nhật schema/fixture có version | Chờ kiểm tra lại |
| R06 | `/predict` chế độ real mặc định chưa suy luận; mock chỉ tạo dữ liệu tổng hợp | Cao | BACKEND `Phuc1232`, #37/#38 | Giữ 503 trung thực đến khi tích hợp artifact; không dùng mock qua gate | Giới hạn đã biết |
| R07 | [PR #65](https://github.com/ngnsusinn/anti-fake-news/pull/65) đã sửa trích chữ ẩn bằng CSS, chạy lại 2/2 test phiên, Chromium smoke và ca hồi quy, rồi merge tại `75a7b32` | Trung bình | EXTENSION, #10/#11; QA | Dùng phiên bản đã merge cho tích hợp và giữ ca hồi quy | Đã kiểm chứng phạm vi tuần 1 |
| R08 | Issue nhắc T01–T12 nhưng `DESIGN.md` §1–4 chưa có đặc tả chi tiết | Trung bình | QA `dangnguyen0512`, #14 | DATA review ma trận QA và khóa phiên bản sau thống nhất | Đã có bản nháp |
| R09 | Theo QA, nhóm đã chốt review 11:30/20:30 và checkpoint 20:30 mỗi cuối tuần; QA chọn khóa Test **13/12** nhưng chưa có giờ/biên bản nhóm chốt ngày này hoặc CODEOWNERS duyệt PR QA | Trung bình | QA `dangnguyen0512` + owner `ngnsusinn`, #13 | Xác nhận ngày/giờ khóa Test và lấy review DATA/CODEOWNER cho PR #69 | Lịch review đã xác nhận; Test lock/review còn mở |
| R10 | DEFINE ghi tiếng Việt nhưng bản API nháp từng đề xuất đầu vào tiếng Anh | Cao | INTEGRATION `fulord26` cùng ML/EXTENSION, #4/#8 | Chốt một phạm vi ngôn ngữ trước khi nghiệm thu fixture/metrics | Chưa thống nhất |

Mốc đề nghị cập nhật blocker tiếp theo: **checkpoint 30/11/2026, 20:30 (giờ Việt Nam)**. Đây là mốc rà tiến độ, không thay thế hạn của từng issue.

Mỗi kỳ review cần bổ sung: URL bằng chứng, tác động đo được, quyết định, người duyệt và mốc xử lý tiếp. Ưu tiên blocker P0 trước khi dùng quỹ dự phòng; không đổi kiến trúc hoặc tự tạo số liệu chỉ để vượt checkpoint.
