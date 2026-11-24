# FakeNewsNet — Báo cáo tổng kết thu hồi và bàn giao 400 mẫu

## Tóm tắt

Lượt pilot và đợt xử lý bổ sung thu được **400 mẫu đạt tiêu chí thu hồi**, gồm 100 mẫu cho mỗi tổ hợp nguồn và nhãn. Trong số đó, **286 mẫu có cả thân bài và ảnh**, 99 mẫu chỉ có thân bài và 15 mẫu chỉ có ảnh.

Một mẫu đạt khi trích được ít nhất một từ trong thân bài hoặc tải được ảnh đại diện và xác minh được định dạng ảnh. Kết quả đối chiếu bài gốc và ngữ cảnh ảnh sẽ được ghi riêng ở bước rà soát chất lượng.

## 1. Phân bố mẫu và đối soát dữ liệu đầu vào

| Nguồn và nhãn | Đầu vào | Hợp lệ | Loại | Chờ | Thiếu thân bài¹ | Thiếu ảnh¹ | Có cả hai¹ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gossipcop_fake | 5323 | 100 | 310 | 4913 | 1 | 17 | 82 |
| gossipcop_real | 16817 | 100 | 106 | 16611 | 2 | 17 | 81 |
| politifact_fake | 432 | 100 | 121 | 211 | 3 | 40 | 57 |
| politifact_real | 624 | 100 | 138 | 386 | 9 | 25 | 66 |
| Tổng | 23196 | 400 | 675 | 22121 | 15 | 99 | 286 |

¹ Ba cột cuối tính trên tập hợp lệ. Có 385 mẫu có thân bài và 301 mẫu có ảnh. Tập hợp lệ gồm 200 fake và 200 real, 200 GossipCop và 200 PolitiFact. Trạng thái chờ dành cho 22.121 bản ghi ngoài phạm vi batch sau khi đã đủ chỉ tiêu. Khả năng thu hồi của các bản ghi này chưa được đo.

## 2. Kết quả xử lý bổ sung và nguyên nhân loại

Pilot cung cấp 228 mẫu đạt. Batch tiếp theo kiểm tra 353 bản ghi đang chờ từ CSV nguồn, thu thêm 172 mẫu và loại 181 mẫu. Số mẫu bổ sung theo thứ tự GossipCop fake, GossipCop real, PolitiFact fake và PolitiFact real lần lượt là 36, 40, 52 và 44. Tỷ lệ đạt của đợt bổ sung là 172/353 (48,73%). Tổng 675 bản ghi bị loại gồm 494 đã loại ở bản pilot và 181 loại thêm. Một phần bị loại qua metadata trước khi gửi yêu cầu mạng.

| Lý do trong manifest | Số bản ghi |
| --- | --- |
| Thiếu cả thân bài lẫn ảnh (`neither_recovered`) | 334 |
| Thiếu URL bài (`missing_url`) | 330 |
| Chuyển về trang chủ (`redirect_home`) | 6 |
| Xung đột nhãn trên cùng ID nguồn (`conflicting_source_id_labels`) | 4 |
| Xác nhận URL dẫn đến bài khác (`confirmed_wrong_article`) | 1 |

## 3. Các mốc dữ liệu bàn giao

Gói validator-snapshots.zip chứa bốn snapshot 228, 300, 350 và 400 mẫu, cùng SHA256SUMS. Các mốc trung gian được tái dựng sau lượt chạy từ thứ tự bản ghi trong nhật ký batch. Snapshot cuối dùng nguyên byte của valid-400.jsonl. Đã đối chiếu tập sample_id ở từng mốc, kiểm tra mốc trước là tập con của mốc sau và xác nhận 400 ID duy nhất. Đối chiếu bằng `sample_id` vì thứ tự dòng của bản chốt có thể khác thứ tự hoàn thành. Validator có thể kiểm tra checksum, trường bắt buộc, khóa duy nhất, điều kiện body hoặc ảnh và phân bố bốn nhóm. Lưu kết quả validator theo phiên bản riêng để bảo toàn bản raw AFN-016.

## 4. Nhận diện sơ bộ nhà xuất bản, ảnh và sự kiện

| Khóa đối chiếu | Khóa có giá trị phân biệt | Nhóm có ≥2 mẫu | Mẫu trong nhóm lặp |
| --- | --- | --- | --- |
| publisher_host | 242 | 57 | 215 |
| image_url_group | 274 | 12 | 39 |
| event_candidate_title | 396 | 4 | 8 |

publisher_host nhận diện cùng hostname nhà xuất bản. image_url_group là hash của URL ảnh và bảng chỉ tính ảnh đã xác minh. Cùng URL là tín hiệu ảnh dùng lại. Ảnh giống nhau qua URL khác cần so sánh bytes hoặc perceptual hash. event_candidate_title gom theo tiêu đề chuẩn hóa. event_id hiện chưa được gán cho cả 400 mẫu nên số nhóm sự kiện độc lập chưa xác định. Một hostname có thể đăng nhiều sự kiện.

## 5. Kế hoạch rà soát và chuẩn bị dữ liệu tuần 2

1. Rà soát chất lượng nội dung đã thu hồi. Bước recovery đã kiểm tra đủ 400 mẫu theo tiêu chí có thân bài hoặc ảnh và xác nhận mỗi nhóm nguồn–nhãn có 100 mẫu. Tuần 2 ưu tiên đối chiếu bài sau chuyển hướng với tiêu đề gốc, rà thân bài quá ngắn và kiểm tra ảnh đại diện có đúng ngữ cảnh. Ghi kết quả audit theo sample_id và lưu ảnh đã duyệt kèm checksum để chuẩn bị tập huấn luyện.
2. Rà các nhóm cùng ảnh hoặc tiêu đề, gán event_id sau đối chiếu và giữ toàn bộ một sự kiện hoặc nội dung trùng trong cùng tập khi chia train/validation/test. Kiểm tra lại phân bố nguồn và nhãn sau khi gom.
3. Dùng 286 ứng viên đủ hai phương thức để chuẩn bị phép so sánh text-only, image-only và đa phương thức trên cùng tập đánh giá. Mỗi nhóm nguồn–nhãn có 57–82 cặp. Nếu audit làm số cặp hợp lệ xuống dưới 200 hoặc còn quá ít sự kiện độc lập trong một nhãn, lấy thêm từ phần chờ, ưu tiên nhóm thiếu và sự kiện mới. Báo cáo số thực tế sau audit. Các snapshot chỉ chứa bản ghi từ CSV nguồn.

## Bàn giao bằng chứng cho QA và AFN-016

Đặt gói snapshot, manifest chốt, bảng đối soát pilot và `SHA256SUMS` ở nơi thành viên
QA và AFN-016 có quyền đọc. Ghi vị trí và SHA-256 chốt trong PR khi bàn giao. Với checksum do DATA ghi riêng, truyền thêm `--expected-final-sha256 <SHA-256>` để đối chiếu gói với bản bàn giao.
Chạy lệnh sau với đường dẫn các snapshot thật theo thứ tự 228, 300, 350 và 400 dòng.

```
python scripts/verify_recovery_snapshots.py --checksums SHA256SUMS --final valid-400.jsonl snapshot-228.jsonl snapshot-300.jsonl snapshot-350.jsonl snapshot-400.jsonl
```

Script đối chiếu checksum, đếm ID duy nhất, kiểm tra quan hệ tập con và so bản 400 dòng
với manifest chốt. Kiểm thử script dùng dữ liệu tổng hợp. Chưa chạy trên gói thật vì
chưa có đường dẫn bàn giao. Cần DATA giải thích chênh lệch giữa 230 ứng viên thu hồi
được ít nhất một phương thức trong báo cáo pilot và 228 mẫu dùng cho batch.

Kiểm tra quyền nguồn, thân bài tiếng Anh và ảnh liên quan theo
[hợp đồng manifest AFN-001](../docs/data-contract.md) (nháp). Lưu riêng báo cáo
đối soát ID của 230 ứng viên và lý do loại từng bản ghi để giải thích mốc 228.
Giữ các bản JSONL thật và nội dung bài/ảnh ở nơi nhóm được phép truy cập.
