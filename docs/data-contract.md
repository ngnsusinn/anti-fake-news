# Hợp đồng manifest AFN-001

Bản nháp v1 cho DATA và Integration review trước khi nghiệm thu nguồn.
[Manifest schema](../data/manifest.schema.json) áp dụng theo từng dòng JSONL.
[Fixture tổng hợp](../tests/data/fixtures/manifest-v1.jsonl) minh họa hai trạng
thái. Đường dẫn và SHA-256 ảnh trong fixture chỉ minh họa cấu trúc.

## Nguồn và phạm vi dùng

Ưu tiên PolitiFact, bổ sung GossipCop khi cần và báo cáo riêng phân bố theo
nguồn. Giữ nhãn `fake`/`real` từ tên nhóm của bốn CSV FakeNewsNet. ID giống nhau
có nhãn khác nhau được đưa vào đối soát, giữ nguyên nguồn nhãn. Tập metadata
được cung cấp riêng với mã thu thập; README FakeNewsNet nêu hạn chế phân phối
toàn bộ nội dung thu hồi. Lưu bằng chứng quyền theo nhà xuất bản và theo tài
nguyên bài/ảnh trước khi đưa mẫu vào nghiên cứu; nếu chưa rõ, giữ pending hoặc
loại với lý do `rights_unverified`. Chỉ chia sẻ nội dung được phép; dùng ID,
một tập trường metadata được phép và hướng dẫn khôi phục cho gói bàn giao.

Nguồn: [FakeNewsNet](https://github.com/KaiDMML/FakeNewsNet#overview) và
[phiếu đăng ký đề tài](../output/pdf/phieu-dang-ky-de-tai-07.pdf).

## Từ bản ghi thu hồi đến mẫu nghiên cứu

- Khóa ổn định `source:label:source_id`; validator phải đối chiếu ba trường
  với khóa và bảo đảm duy nhất trong manifest. Giữ riêng URL gốc và publisher
  đã đối soát. Ghi `retrieved_at` theo UTC tại thời điểm thu nội dung, không
  dùng thời điểm tạo báo cáo thay cho thời điểm thu.
- JSONL `recovery-attempts.jsonl` là nhật ký dev/pilot. Sau kiểm định, DATA tạo
  manifest với `accepted`, `rejected` hoặc `pending`. Chỉ `accepted` đủ điều
  kiện dùng tiếp, trường `is_fixture` bắt buộc là `false` với dữ liệu thật.
- Duyệt thân bài tiếng Anh, không rỗng, tối đa 50.000 ký tự, tiêu đề tùy chọn tối
  đa 500 ký tự. Chọn đúng một ảnh liên quan đã giải mã được, JPEG/PNG, tối đa
  10 MiB và 20 megapixel, lưu đường dẫn nội bộ và SHA-256.
- Mẫu bị loại có `exclusion_reason`; không loại dựa trên kết quả dự đoán.
  `event_id`/`group_id` có thể rỗng trước bước gom nhóm #17. Khi chia tập #18,
  mỗi mẫu nghiên cứu phải có group ID đã audit.
