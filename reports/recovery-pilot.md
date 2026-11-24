# Báo cáo recovery pilot FakeNewsNet

**Ngày chạy** 20/11/2026, giờ Việt Nam

**Kết quả chính** 400 bản ghi đầu vào, 242 JSON bài, 217 thân bài và 178 ảnh tải thành công. Có **165/400 mẫu (41,25%)** thu được đủ tiêu đề trích xuất, thân bài và một ảnh ứng viên.

## 1. Phạm vi và nguồn

Pilot xử lý đủ bốn CSV người dùng cung cấp, mỗi nhóm 100 bản ghi. Hai nguồn dữ liệu là GossipCop và PolitiFact, mỗi nguồn có hai nhãn gốc `fake` và `real`. Nhãn được giữ theo CSV nguồn. 400 là số bản ghi thực tế của lượt chạy.

Lượt chạy chỉ khảo sát URL bài có trong metadata đã cung cấp, các URL chuyển hướng, Wayback và ảnh đại diện do collector trả về. Đây là truy cập HTTP thông thường. Phản hồi chặn hoặc yêu cầu đăng nhập được ghi nhận theo kết quả truy cập. Quyền tải, lưu và sử dụng nội dung hoặc ảnh theo từng nhà xuất bản chưa được xác minh trong hồ sơ pilot. Vì vậy, tiêu chí **nguồn được phép sử dụng cho bộ dữ liệu** cần bằng chứng riêng trước khi đưa nội dung vào huấn luyện hoặc phân phối.

## 2. Cách thu hồi

1. Đọc bốn CSV, giữ ID gốc, nguồn, nhãn, tiêu đề trong CSV và URL gốc. Bỏ qua yêu cầu mạng đối với 10 URL trống và ghi lý do.
2. Gọi trực tiếp `crawl_news_article` trong mã FakeNewsNet của tác giả, dùng Newspaper3k 0.2.8. Với URL thiếu giao thức, collector thử HTTP rồi HTTPS khi lần đầu thất bại. Khi collector chưa thu được bài, nó tra Wayback CDX và thử bản lưu đầu tiên được trả về nếu có.
3. Lấy `title`, `text`, `top_img` và metadata từ kết quả collector. Ghi JSON theo nhóm và ID. Thân bài được tính khi trường `text` có ít nhất một từ. Tiêu đề metadata và tiêu đề trích được lưu riêng để đối chiếu.
4. Tải riêng một ảnh theo `top_img`. Thành công khi nhận được dữ liệu ảnh raster xác minh được bằng Pillow, giới hạn 12 MB. Pilot xác minh ảnh trong bộ nhớ. File ảnh chưa được lưu riêng trong đầu ra.
5. Chạy 24 luồng. Yêu cầu chưa có timeout được đặt giới hạn kết nối 8 giây và đọc 12 giây. Newspaper3k giữ timeout mặc định riêng cho các yêu cầu nội bộ. Chuỗi thử URL và Wayback hữu hạn theo collector. Lượt này chưa có chính sách retry lỗi tạm thời có backoff hoặc hạn chót cho toàn bộ một mẫu.

[Mã collector tại commit 654361e1c8d5baa751baf1dac5032df621652280](https://github.com/KaiDMML/FakeNewsNet/blob/654361e1c8d5baa751baf1dac5032df621652280/code/news_content_collection.py)

## 3. Kết quả thực tế

| Nhóm            |     Mẫu | Yêu cầu bài đầu tiên trả 2xx | Có JSON | Có title trích | Có body | Thiếu body | Có URL ảnh | Tải được ảnh | Thiếu ảnh | Có title, body và ảnh |
| --------------- | ------: | ---------------------------: | ------: | -------------: | ------: | ---------: | ---------: | -----------: | --------: | --------------------: |
| gossipcop_fake  |     100 |                           52 |      66 |             66 |      64 |         36 |         65 |           54 |        46 |                    53 |
| gossipcop_real  |     100 |                           59 |      64 |             63 |      58 |         42 |         62 |           49 |        51 |                    47 |
| politifact_fake |     100 |                           42 |      51 |             48 |      46 |         54 |         45 |           30 |        70 |                    28 |
| politifact_real |     100 |                           61 |      61 |             59 |      49 |         51 |         50 |           45 |        55 |                    37 |
| **Tổng**        | **400** |                      **214** | **242** |        **236** | **217** |    **183** |    **222** |      **178** |   **222** |               **165** |

- **Truy cập trang:** 214/390 URL đã gửi yêu cầu có phản hồi 2xx ở yêu cầu bài đầu tiên, sau khi theo chuyển hướng (54,87%). Tính trên toàn bộ pilot, tỷ lệ là 214/400 (53,50%). Chỉ số này gồm URL Wayback có sẵn trong CSV và đo phản hồi HTTP. Một phản hồi 2xx vẫn có thể dẫn tới trang khác.
- **Thu hồi bài:** 242/400 JSON (60,50%) và 217/400 thân bài (54,25%). Trong số các JSON thu được, 30 đến từ bước tra cứu bản lưu sau khi collector không thu được bài ở URL đầu vào.
- **Thu hồi ảnh:** 178/400 mẫu (44,50%). Với 222 mẫu có `top_img`, tỷ lệ tải và xác minh được ảnh là 178/222 (80,18%).
- **Phạm vi thí nghiệm:** 217 mẫu có body cho text-only, 178 mẫu có ảnh cho image-only và 165 mẫu có cả hai cho đa phương thức. Gộp theo khóa nhóm và ID, 230 mẫu thu được ít nhất một phương thức, gồm 52 chỉ có body, 13 chỉ có ảnh và 165 có cả hai. Có 170 mẫu thiếu cả hai.
- **Thời gian:** Khoảng **8 phút 57 giây** từ lúc tạo nhật ký kết quả (19:06:01) đến lần ghi cuối (19:14:58). Đây là ước lượng thời gian chạy song song theo mốc filesystem. Hồ sơ chưa đo thời lượng riêng của từng mẫu.

## 4. Mẫu thất bại và nguyên nhân

| Kết quả                                                 |  Số mẫu |
| ------------------------------------------------------- | ------: |
| Thiếu body vì URL trống                                 |      10 |
| Thiếu body vì collector không trả JSON sau khi thử URL  |     148 |
| Thiếu body vì JSON có trường text rỗng                  |      25 |
| **Tổng thiếu body**                                     | **183** |
| Thiếu ảnh vì URL bài trống hoặc không thu được JSON bài |     158 |
| Có JSON nhưng không có top_img                          |      20 |
| top_img trả HTTP 404                                    |      20 |
| top_img trả HTTP 403                                    |      11 |
| top_img trả HTTP 503                                    |       4 |
| Dữ liệu tải về không giải mã được thành ảnh raster      |       7 |
| top_img không phải URL HTTP(S)                          |       2 |
| **Tổng thiếu ảnh**                                      | **222** |

CSV chi tiết ghi URL và mã HTTP của từng lần thử ghi nhận được, kết quả Wayback, lỗi parser nếu có, và lý do riêng cho thân bài và ảnh. Với bài không có JSON, các trường hợp quan sát được gồm HTTP 403, 404, 402, 503, timeout và lỗi Newspaper3k/lxml. Khi URL bài hoặc CDX trả lỗi, số liệu phản ánh môi trường và thời điểm chạy.

## 5. Provenance, định danh và khả năng chạy lại

| Tiêu chí                           | Bằng chứng và trạng thái                                                                                                                                                                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Giữ nguồn và nhãn                  | CSV kết quả giữ nhóm nguồn và nhãn, ID gốc, tiêu đề CSV, URL gốc, URL collector trả về, URL cuối, canonical, tiêu đề trích, URL ảnh và kết quả Wayback.                                                                                   |
| Khóa duy nhất trong pilot          | Có 400 khóa `(nhóm, ID)` duy nhất, nhưng chỉ 399 ID gốc duy nhất. `politifact14940` xuất hiện ở cả `politifact_fake` và `politifact_real`, cùng URL và tiêu đề. Cần rà soát xung đột nhãn trước khi chia tập.                             |
| Chạy lại không tạo sample_id trùng | Lượt này lưu JSON theo nhóm và ID. Chưa có cột `sample_id` riêng hoặc test chạy lại. Dùng khóa `<source>:<label>:<source_id>` để upsert theo cùng khóa, đồng thời kiểm tra trùng nội dung giữa các nhãn.                                  |
| Resume                             | Chưa được kiểm chứng. Trình chạy hiện mở lại nhật ký ở chế độ ghi mới và gửi lại toàn bộ mẫu. Tiêu chí nghiệm thu là ngắt giữa lượt, chạy lại, bỏ qua mẫu đã hoàn tất, tiếp tục mẫu còn thiếu và xác nhận đúng 400 khóa sau khi chạy lại. |
| Thời gian lấy từng mẫu             | Hồ sơ có thời điểm của cả lượt chạy, nhưng chưa ghi `fetched_at` và thời lượng theo mẫu hoặc theo từng lần thử. Cần ghi timestamp UTC khi tải bài và ảnh, kể cả khi yêu cầu thất bại, cùng thời lượng từng lần thử.                       |
| Thu hồi title/body/ảnh             | Đã đo khả năng trích title/body và tải xác minh một ảnh. JSON bài đã ghi ra đĩa. Việc lưu file ảnh, đường dẫn và checksum để tái sử dụng chưa được thực hiện trong lượt này.                                                              |

## 6. Diễn giải kết quả

Lượt dùng mã tác giả có 165 mẫu đa phương thức ứng viên. Đối chiếu theo khóa nhóm và ID với lượt thử trước, 105 mẫu đạt ở cả hai lượt, 60 mẫu chỉ đạt ở lượt tác giả và 18 mẫu chỉ đạt ở lượt trước. Khi áp lại ngưỡng tối thiểu 50 từ cho lượt tác giả, còn 146 mẫu có body và ảnh. Hai lượt có cách chọn ảnh khác nhau nên chênh lệch phản ánh cả quy trình kiểm tra lẫn khả năng truy cập.

Cần xác nhận bài và ảnh đúng ngữ cảnh trước khi chốt tập huấn luyện. Chẳng hạn, URL của `gossipcop-3594957031` chuyển sang một bài khác về Taylor Swift và vẫn trả về cả text lẫn ảnh. Vì vậy, **165 là số mẫu thu được đủ dữ liệu kỹ thuật để rà soát**, còn số mẫu được duyệt để huấn luyện chưa được xác định.

## Tệp đối chiếu

- [Chi tiết 400 mẫu theo mã tác giả](https://chatgpt.com/library?file_id=libfile_8d7d46a4dea48191a97a70f0dd321c0a&account_id=personal)
- [Báo cáo lượt chạy mã tác giả](https://chatgpt.com/library?file_id=libfile_e125de485c748191b49c2413b5a4c499&account_id=personal)
- [Chi tiết lượt kiểm tra ban đầu](https://chatgpt.com/library?file_id=libfile_9cb06b2c88f88191976513b0d71079d4&account_id=personal)

## Kiểm tra chạy tiếp và đối soát bản ghi

Phiên bản script cập nhật nhận tham số tùy chọn `--repo`, tách cache theo checksum của
bốn CSV, bỏ qua các JSON đọc được đã có và dùng lại ảnh đã lưu. Báo cáo cục bộ
`validation_reports/recovery-attempts.jsonl` có một dòng theo khóa `source:label:source_id`
cho mỗi bản ghi. Báo cáo ghi URL nguồn, trạng thái, lý do thiếu và thời điểm ghi UTC.
Các trường `article_saved_at` và `image_saved_at` lấy từ thời điểm sửa tệp cục bộ.

Bộ kiểm thử tổng hợp mô phỏng ngắt collector sau mẫu đầu tiên và xác nhận lần chạy tiếp
không gửi lại mẫu đó. Số pilot ở trên giữ nguyên. Còn cần xác nhận đầu vào được phép theo
AFN-001, chạy lại với bộ nguồn đã duyệt và bàn giao manifest riêng cho AFN-003.
