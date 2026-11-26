# AFN-059 · Báo cáo tổng hợp và tình trạng nghiệm thu

**26/11/2026 · Bản tổng hợp đang chờ nghiệm thu.** QA `dangnguyen0512`,
reviewer ML `0xDa1Vu`. Snapshot [`aefb0ef`](https://github.com/ngnsusinn/anti-fake-news/commit/aefb0efc2b18fbb3a06d1766d1471ec188933eaf).

## Phương pháp và dữ liệu

Dự án so sánh hồi quy logistic trên ba biểu diễn của bài tiếng Anh kèm một ảnh:
TF-IDF, CLIP ViT-B/32 và TF-IDF + CLIP. Lấy nhãn nguồn FakeNewsNet từ hai phân
tập PolitiFact và GossipCop. Chia theo nhóm, fit trên Train, chọn C/ngưỡng
theo Macro-F1 trên Validation và khóa cấu hình trước Test. Giao thức dùng seed
42, quy trình `afn-preprocess-v1` và không refit trên Train + Validation.
[Giao thức](../docs/experiment-protocol.md) · [Data card](../docs/data-card.md)

Bản ứng viên `ml-v2` dùng 153 Train, 32 Validation, 33 dòng Test đang khóa.
Run lựa chọn `20261126T024649Z`. Bản DATA 352 mẫu là mốc đối soát thu hồi. Số liệu huấn luyện lấy từ `ml-v2`. Audit ghi 21 hostname publisher xuất hiện
ở nhiều split và thiếu event ID. Cùng nguồn giữa các tập và tập Test nhỏ hạn
chế khả năng suy rộng. [Tổng hợp dữ liệu #46](final-data-summary.md) ·
[Tái tạo #48](data-reproduction.md) · [Audit #29](leakage-audit.md)

## RQ1–RQ3

| Câu hỏi | Phép đo đã định | Trạng thái |
| --- | --- | --- |
| RQ1 · Ba cấu hình khác nhau thế nào? | Macro-F1, accuracy, precision/recall/F1/support từng lớp và ma trận trên cùng ID. | Chưa chấm Test. [Kế hoạch và nguồn số liệu #51](model-results.md) |
| RQ2 · Ảnh thay đổi kết quả bao nhiêu? | Δ Macro-F1 có dấu = Multimodal − Text-only; đối chiếu sai khác theo lớp. | Chưa có Δ Test. Chờ #50 và audit #58. |
| RQ3 · Khi nào hai cấu hình bất đồng? | Đối chiếu hai cấu hình theo ID, đếm cả hai đúng/sai và hai nhóm chỉ một mô hình đúng. | [#47](error-analysis.md) đã có phương pháp và kiểm thử fixture. Chưa có phân tích lỗi Test. |

Ứng viên hoàn tất lựa chọn và kiểm parity trên Validation. Bằng chứng
Validation phục vụ chọn cấu hình. Bundle đã qua xác minh hash và loader. Đã đối chiếu manifest/split
Train/Val và `ml.freeze verify --allow-unsigned` đã đạt. Hồ sơ chờ QA ký. #50 và [audit #58](evaluation-audit.md) còn chờ. Việc diễn giải
chỉ áp dụng cho nhiệm vụ phân loại đối chiếu nhãn nguồn. `fake_score` chưa
hiệu chuẩn thành xác suất. Kiểm chứng sự thật và phát hiện ảnh chỉnh sửa
cần bằng chứng và quy trình riêng.

## Demo, hiệu năng và truy vết yêu cầu

Bản đóng gói mở popup từ tab hiện tại, tự trích xuất nội dung, tự chọn ảnh
và gửi multipart khi bấm Phân tích. API v0.2.0 chạy loopback. Kết quả hiển
thị nhãn và điểm, kèm model version, thời gian và chi tiết khi mở. Luồng
sửa/dán văn bản và chọn/tải ảnh trong thiết kế chưa đi qua popup đóng gói.
[Đối chiếu demo #43](e2e-real-model.md) · [Rà quyền, CORS và riêng tư #44](security-privacy-review.md)

Benchmark #52 ở Windows 11/Python 3.13 với bản ứng viên
`multimodal-20261125-105d5f14e79a` đo 20 request sau warm-up, median 110 ms ở
server và 118,79 ms HTTP. Mốc 10 giây đã đạt ở lần đo này. Hồ sơ cuối dùng
model version ngày 26/11 và cần phép đo trên máy demo với bundle cùng hash.
[Log và phương pháp #52](performance.md)

| Yêu cầu | Ca | Trạng thái và bằng chứng |
| --- | --- | --- |
| F01 · Tab nguồn | T01 | Popup lấy tab active. Chờ diễn tập nhiều tab cùng gói. [#43](e2e-real-model.md) |
| F02 · Trích/sửa/dán | T02 | Trích xuất có trong popup. Sửa/dán chờ chốt UI. [#43](e2e-real-model.md) |
| F03 · Chọn ảnh | T03 | Tự chọn ảnh. Chọn/tải tay chờ chốt UI. [#43](e2e-real-model.md) |
| F04 · Kiểm đầu vào | T04–T05 | Có bằng chứng API v0.2.0 trên fixture. Còn xác nhận hành vi bản demo. [#28](api-contract-results.md) |
| F05 · Gọi API | T06 | Unit xác nhận multipart và UUID. Chờ cùng bản demo. [#43](e2e-real-model.md) |
| F06 · Kết quả | T07 | UI có các trường. Chờ kiểm model version trên gói thật. [#43](e2e-real-model.md) |
| F07 · Phục hồi | T08–T09 | Unit xác nhận lỗi và vòng đời. Giữ input và lỗi runtime cần diễn tập. [#43](e2e-real-model.md) |
| F08 · Thực nghiệm | T10–T11 | Có audit Train/Val và giới hạn nguồn. Test chờ freeze, kết quả và audit. [#29](leakage-audit.md) · [#58](evaluation-audit.md) |
| NFR · Trích xuất, tốc độ và riêng tư | T12 | Chờ bộ 10 trang, benchmark cùng bundle và đối chiếu quyền/CORS của gói demo. [#44](security-privacy-review.md) · [#52](performance.md) |

Các mã F01–F08 trong DEFINE tương ứng FR-01–FR-08 trong backlog.
[Ma trận gốc](../docs/test-plan.md) · [Thiết kế](../DESIGN.md) · [Sơ đồ](../DIAGRAMS.md)

## Điều kiện ký báo cáo

DATA bàn giao và xác nhận quyền chia sẻ chỉ mục #48. ML và QA ký freeze
#49. ML bàn giao #50 và Integration cập nhật RQ1–RQ3 ở #51 sau audit #58.
Backend xác nhận benchmark #52 trên máy demo cùng gói. QA đối chiếu lại ma
trận và phiên bản rồi chuyển ML review. [Chỉ mục bàn giao](../release/release-index.json)
