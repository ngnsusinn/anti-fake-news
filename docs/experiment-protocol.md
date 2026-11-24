# Giao thức thực nghiệm AFN-004

Bản đề xuất để Integration và ML rà trước khi khóa. Tham số cho runner ở
[experiment.yaml](../configs/experiment.yaml).

## Phạm vi và chia dữ liệu

[Phiếu đăng ký đề tài](../output/pdf/phieu-dang-ky-de-tai-07.pdf) quy định
mỗi mẫu có thân bài tiếng Anh, tiêu đề tùy chọn và một ảnh đại diện. Giao diện
demo dùng tiếng Việt. Cả ba cấu hình dùng cùng manifest, cùng ID và cùng split.

| Cấu hình | Đặc trưng |
| --- | --- |
| Text-only | TF-IDF tiêu đề và thân bài |
| Image-only | Embedding CLIP ViT-B/32 frozen, chuẩn hóa L2 |
| Multimodal | CSR hstack theo thứ tự TF-IDF rồi CLIP |

Chia theo `group_id` với tỷ lệ mục tiêu 70/15/15 và seed 42. Nhóm liên quan hoặc
mẫu trùng không được xuất hiện ở nhiều tập. Ghi số mẫu, nhãn, nguồn, nhóm và tỷ lệ
thực tế của mỗi tập. Trường hợp thiếu lớp hoặc thiếu nhóm dùng được phải báo
để quyết định phạm vi, giữ nguyên nhóm và dừng đánh giá chính thức đến khi có
phương án được duyệt.

## Tiền xử lý và lựa chọn

Dùng `afn-preprocess-v1` trên Train, Validation, Test và inference. Đếm theo
khoảng trắng sau chuẩn hóa, giữ tối đa 1.500 từ của thân bài. Tiêu đề được giữ
riêng, không tính vào mức này. Nối tiêu đề đã chuẩn hóa và thân bài bằng newline
khi tiêu đề có nội dung. Mức 50.000 ký tự của API áp dụng ở tầng vận chuyển.

Chỉ fit TF-IDF và Logistic Regression trên Train. Mỗi cấu hình thử các cặp C
và ngưỡng trong YAML trên cùng Validation. Dùng xác suất cho lớp `fake` tra
qua `classes_` và gán `fake` khi điểm lớn hơn hoặc bằng ngưỡng. Tính Macro-F1
đều cho hai nhãn `fake`, `real`. So sánh điểm sau khi làm tròn 12 chữ số thập
phân. Khi hòa, ưu tiên ngưỡng gần 0,5 hơn, rồi C nhỏ hơn, rồi ngưỡng thấp hơn.
Dùng `liblinear`, L2 và `class_weight: balanced`; trọng số lấy từ nhãn Train.
Ghi cả điểm Validation và cảnh báo hội tụ. Không fit lại trên Train+Validation.

## Mở Test và phân tích

Trước khi ký freeze chỉ audit metadata: số lượng, định danh, trùng nhóm và hash.
Khóa manifest, split, mã, preprocessing, artifact, C/ngưỡng và mapping nhãn ở
#49 trước #50. Sau khóa, chạy một lượt Test theo giao thức, lưu dự đoán từng ID
và báo Macro-F1, các điểm từng lớp, ma trận nhầm lẫn và chênh lệch Macro-F1
Multimodal trừ Text-only. Ghi lý do và bằng chứng nếu phải chạy lại vì lỗi kỹ thuật.

RQ3 dùng cặp dự đoán của hai cấu hình trên cùng Test. Đếm bốn nhóm cả hai đúng,
chỉ Text-only đúng, chỉ Multimodal đúng và cả hai sai. Trong hai nhóm bất đồng,
tổng hợp theo nhãn, nguồn, nhóm sự kiện và cờ chất lượng dữ liệu đã gắn theo
quy tắc trước Test. Không điều chỉnh đặc trưng hay ngưỡng từ bước phân tích này.
