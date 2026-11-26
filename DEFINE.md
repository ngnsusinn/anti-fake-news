# Đề tài 07 · Phát hiện tin giả dựa trên bài viết và hình ảnh

## 1. Vấn đề và mục tiêu

Người đọc, biên tập viên và người kiểm duyệt cần ưu tiên những bài có dấu hiệu sai lệch để xác minh. Ảnh có thể cung cấp thông tin bổ sung, tạo ấn tượng sai hoặc được tái sử dụng trong ngữ cảnh khác. Hệ thống học từ bài viết có nhãn để dự đoán `fake` hoặc `real` cho một thân bài kèm ảnh đại diện.

## 2. Người dùng và luồng sử dụng

| Đối tượng | Nhu cầu | Đầu ra |
| --- | --- | --- |
| Người đọc | Kiểm tra bài đang xem | Dự đoán và điểm nghi vấn |
| Biên tập viên, người kiểm duyệt | Ưu tiên bài cần xác minh | Kết quả gắn với bài và ảnh đã chọn |
| Nhóm nghiên cứu | Đo đóng góp của ảnh | Bảng so sánh ba cấu hình và phân tích lỗi |

Người dùng mở bài viết, bấm biểu tượng extension và xem trang phân tích của extension. Trang này hiển thị văn bản đã trích và ảnh ứng viên. Người dùng sửa văn bản, chọn một ảnh rồi bấm phân tích. Extension gửi nội dung đã xác nhận tới API cục bộ và hiển thị kết quả.

Khi trang khó trích xuất hoặc ảnh bị chặn, người dùng dán thân bài và tải ảnh trong cùng giao diện. Đầu vào có thể đến từ nhiều nền tảng. Khả năng trích xuất tự động được kiểm tra trên bộ trang cụ thể.

## 3. Phạm vi

| Thành phần | Phạm vi bàn giao |
| --- | --- |
| Ngôn ngữ | Bài viết tiếng Anh, giao diện tiếng Việt |
| Đơn vị phân tích | Tiêu đề, thân bài viết, body của 1 trang thông tin |
| Nhãn | `fake` và `real` theo nguồn dữ liệu |
| Trình duyệt | Trình duyệt xây dựng dựa trên Chromium |
| Giao diện | Extension Manifest V3 với trang phân tích riêng |
| Suy luận | Mô hình chạy trực tiếp ngay trên máy |
| Dữ liệu | Tập con FakeNewsNet, mục tiêu 200–500 bài hợp lệ |
| Mô hình | Hồi quy logistic trên văn bản, ảnh và đặc trưng kết hợp |
| Cài đặt | Extension unpacked và API khởi động theo hướng dẫn |

Các hướng sau 4 tuần gồm tiếng Việt, nhiều ảnh, OCR, phát hiện vùng chỉnh sửa, truy tìm ảnh gốc, kiểm chứng bằng nguồn ngoài và phát hành lên cửa hàng extension.

## 4. Yêu cầu chức năng

| Mã | Yêu cầu | Điều kiện chấp nhận |
| --- | --- | --- |
| F01 | Chạy từ bài đang xem | Ghi nhận tab và URL gốc khi bấm extension |
| F02 | Trích tiêu đề và thân bài | Có bản xem trước chỉnh sửa được và phương án dán thủ công |
| F03 | Chọn ảnh | Extension tự động detect ảnh ở trong bài viết (nếu có)|
| F04 | Kiểm tra đầu vào | Báo thân bài thiếu, ảnh lỗi, ảnh hoặc văn bản quá lớn |
| F05 | Gọi API | Chỉ khi bấm vào extension |
| F06 | Hiển thị kết quả | Có nhãn, điểm nghi vấn, phiên bản mô hình và thời gian |
| F07 | Phục hồi lỗi | Giữ bản nhập khi API tắt hoặc hết thời gian chờ |
| F08 | Thực nghiệm | Ba cấu hình dùng cùng tập chia và có kết quả tái tạo được |

Điểm nghi vấn là đầu ra mô hình cho lớp fake. Giao diện dùng cụm “Mô hình dự đoán” và nhắc người dùng đối chiếu bằng chứng. Với nguồn và chủ đề mới, chất lượng dự đoán cần được kiểm chứng riêng.

## 5. Dữ liệu và điều kiện chốt

Dùng nhãn và URL của FakeNewsNet để khôi phục thân bài và ảnh. Ưu tiên PolitiFact, bổ sung GossipCop khi cần và ghi rõ phân bố mẫu theo phân tập. Khả năng tải lại bài và ảnh cần kiểm tra ngay đầu tuần 1. [FakeNewsNet](https://github.com/KaiDMML/FakeNewsNet)

Mỗi mẫu phải có liên kết tới bản ghi nhãn, thân bài và ảnh đọc được. Loại trang đã đổi nội dung, lỗi truy cập, ảnh logo hoặc quảng cáo chọn nhầm. Khi rà mẫu, phân biệt bài gốc cần phân loại với trang kiểm chứng dùng để xác định nhãn. Lưu số mẫu tải được, lý do loại và thời điểm thu thập.

| Mốc | Điều kiện và quyết định |
| --- | --- |
| Ngày 2 | Thử ít nhất 30 URL, ước tính tỷ lệ lấy được cả thân bài và ảnh |
| Cuối tuần 1 | Chốt mục tiêu 200–500 mẫu và danh sách train/validation/test |
| Dưới 200 mẫu | Tiến hành nghiên cứu thăm dò nếu mỗi tập vẫn có đủ hai lớp và nhóm độc lập |
| Không đủ lớp hoặc nhóm độc lập | Ghi nhận trở ngại dữ liệu, điều chỉnh kế hoạch trước khi kết luận chất lượng |

Bộ bàn giao chứa mã bài, tập chia, hướng dẫn khôi phục và các ví dụ được phép chia sẻ. Điều kiện sử dụng nội dung và ảnh phải được rà theo từng nguồn.

## 6. Định nghĩa trọng tâm hình ảnh

Ảnh là đầu vào bắt buộc của mô hình kết hợp. Mô hình chỉ ảnh giúp xác định lượng thông tin mà ảnh cung cấp. Đối chiếu mô hình kết hợp với chỉ văn bản giúp đo ảnh cải thiện hoặc làm giảm chất lượng như thế nào.

Phân tích thêm một số ca hoán đổi ảnh cùng chủ đề để khảo sát độ nhạy. Các cặp đã sửa cần được xem xét lại nhãn trước khi dùng để tính độ chính xác. Kiến trúc cơ sở ghép đặc trưng phù hợp khối lượng 4 tuần, khả năng học quan hệ chi tiết giữa câu văn và vùng ảnh còn hạn chế.

## 7. Tiêu chí nghiệm thu

| Nhóm | Tiêu chí |
| --- | --- |
| Dữ liệu | Manifest cố định, thống kê từng lớp và phân tập, kiểm tra trùng giữa các tập |
| Mô hình | Chạy ba cấu hình và lưu mô hình, cấu hình, ngưỡng cùng bộ test |
| Kết quả | Macro-F1, precision/recall theo lớp, ma trận nhầm lẫn và chênh lệch so với chỉ văn bản |
| Demo | Hoàn thành từ mở trang, sửa bài, chọn ảnh đến nhận kết quả |
| Lỗi | Có xử lý API tắt, ảnh lỗi, trang bị hạn chế và thân bài trống |
| Phân tích | Rà ít nhất 10 ca nếu đủ ca phù hợp, gồm cả trường hợp dự đoán đúng |
| Tái tạo | Có hướng dẫn cài đặt, phiên bản thư viện, seed và danh sách tập chia |

Mục tiêu trích xuất là ít nhất 8/10 trang bài viết thông thường trong bộ nghiệm thu đã chọn trước. Kiểm tra thủ công tiêu đề, thân bài và ảnh. Mục tiêu suy luận sau khi tải mô hình là trung vị dưới 10 giây trên máy demo, đo tối thiểu 20 lượt và ghi cấu hình máy. Báo cáo kết quả thực tế, gồm cả trường hợp thêm ảnh giảm chất lượng.

## 8. Kế hoạch 4 tuần

| Tuần | Dữ liệu và mô hình | Extension và API | Bàn giao |
| --- | --- | --- | --- |
| 1 | Kiểm tra tải dữ liệu, lọc trùng, chia tập | Chốt API, dựng extension trích văn bản | Manifest và khung extension |
| 2 | Trích đặc trưng, huấn luyện ba cấu hình | API đọc mô hình và nhận ảnh, văn bản | Mô hình và API chạy thật |
| 3 | Rà validation, đóng băng mô hình và ngưỡng | Tích hợp ảnh, xử lý lỗi, cài unpacked | Demo chạy trọn luồng |
| 4 | Chạy test cuối, phân tích đóng góp ảnh | Kiểm thử trang, hiệu năng, hướng dẫn | Báo cáo, mã nguồn, mô hình |

Nếu làm một người, thực hiện theo thứ tự phụ thuộc. Nếu làm nhóm, phân vai dữ liệu, mô hình và extension/API, cùng rà kết quả cuối. Số thành viên hiện chưa được xác định.

## 9. Rủi ro và phương án xử lý

| Rủi ro | Dấu hiệu | Phương án |
| --- | --- | --- |
| Bài hoặc ảnh mất | Tỷ lệ khôi phục thấp ngày 2 | Mở rộng trong FakeNewsNet, chốt tập nhỏ có thể đánh giá |
| Sai lệch nguồn | Tên miền hoặc phân tập gần như chỉ có một nhãn | Thống kê phân bố, bỏ metadata khỏi đầu vào, rà lỗi theo nguồn |
| Ảnh bị chặn | CDN trả lỗi, yêu cầu đăng nhập hoặc quyền bị từ chối | Tải ảnh thủ công, giữ nội dung bài |
| Trích sai bài | Menu, bình luận hoặc nhiều bài bị ghép | Cho sửa thân bài, kiểm thử bộ trang cố định |
| Quá khớp | Validation thấp hoặc biến động | Giới hạn đặc trưng, điều chuẩn, cố định bộ mã hóa ảnh |
| Chậm tích hợp | Cuối tuần 3 chưa có luồng hoàn chỉnh | Chốt Chrome và một luồng extension/API |

## 10. Cơ sở tham khảo

- Nghiên cứu đối chiếu đơn phương thức và đa phương thức trên Fakeddit. [Segura-Bedmar và Alonso-Bartolome, 2022](https://doi.org/10.3390/info13060284)
- Tổng quan các hướng phát hiện tin giả đa phương thức và khả năng giải thích. [Nasser và cộng sự, 2025](https://doi.org/10.1016/j.rineng.2025.104752)
- Danh mục tài nguyên để khảo sát các nhóm dữ liệu. [Cheung](https://github.com/thcheung/awesome-fake-news-datasets)

Chi tiết triển khai nằm trong [DESIGN.md](DESIGN.md).

## Tình trạng nghiệm thu ngày 26/11/2026

Luồng phát hành hiện mở popup một nút, tự trích nội dung và chọn ảnh. F02–F03
và F07 còn cần xác nhận các tiêu chí sửa/dán, chọn/tải tay và giữ bản nhập
trên gói demo. F08 đã có freeze đủ chữ ký và audit Test qua 33/33 ID, chờ ML review. [Truy vết F01–F08 và T01–T12](reports/final-report.md#demo-hiệu-năng-và-truy-vết-yêu-cầu)
