# AFN-059 · Báo cáo tổng hợp và tình trạng nghiệm thu

**26/11/2026 · Bản tổng hợp đang chờ nghiệm thu.** QA `dangnguyen0512`,
reviewer ML `0xDa1Vu`. Snapshot [`4175c97`](https://github.com/ngnsusinn/anti-fake-news/commit/4175c974e69d9364aff4428aade3acb7e39f4824).

## Phương pháp và dữ liệu

Dự án so sánh hồi quy logistic trên ba biểu diễn của bài tiếng Anh kèm một ảnh:
TF-IDF, CLIP ViT-B/32 và TF-IDF + CLIP. Lấy nhãn nguồn FakeNewsNet từ hai phân
tập PolitiFact và GossipCop. Chia theo nhóm, fit trên Train, chọn C/ngưỡng
theo Macro-F1 trên Validation và khóa cấu hình trước Test. Giao thức dùng seed
42, quy trình `afn-preprocess-v1` và không refit trên Train + Validation.
[Giao thức](../docs/experiment-protocol.md) · [Data card](../docs/data-card.md)

Bản `ml-v2` đã ký dùng 153 Train, 32 Validation và 33 Test (17 fake, 16 real, 33 nhóm).
Run lựa chọn `20261126T024649Z`. Bản DATA 352 mẫu là mốc đối soát thu hồi. Số liệu huấn luyện lấy từ `ml-v2`. Audit ghi 21 hostname publisher xuất hiện
ở nhiều split và thiếu event ID. Cùng nguồn giữa các tập và tập Test nhỏ hạn
chế khả năng suy rộng. [Tổng hợp dữ liệu #46](final-data-summary.md) ·
[Tái tạo #48](data-reproduction.md) · [Audit #29](leakage-audit.md)

## RQ1–RQ3

ML chấm #50 một lượt sau khi freeze #49 được merge. QA tái tính từ
predictions đã lưu của cả ba mô hình trên cùng 33 ID. Các giá trị dưới đây
đã đối chiếu với artifact tổng hợp. [PR #123](https://github.com/ngnsusinn/anti-fake-news/pull/123) ·
[Audit #58](evaluation-audit.md)

| RQ1 · Cấu hình | Macro-F1 | Accuracy | Ma trận nhầm lẫn `[[fake→fake, fake→real], [real→fake, real→real]]` |
| --- | ---: | ---: | --- |
| Text-only | 0,8167 | 0,8182 | `[[12, 5], [1, 15]]` |
| Image-only | 0,5696 | 0,6364 | `[[17, 0], [12, 4]]` |
| Multimodal | 0,7232 | 0,7273 | `[[10, 7], [2, 14]]` |

**RQ2.** Trên Test này, Multimodal thấp hơn Text-only **9,35 điểm phần trăm
Macro-F1** (Δ = −0,0935). Image-only nhận đúng 17/17 fake và 4/16 real.
Mỗi mẫu làm accuracy đổi khoảng 3 điểm phần trăm, nên kết quả chưa đủ
để kết luận về ý nghĩa thống kê hay hiệu năng trên nguồn mới.

| RQ3 · Nhãn nguồn | Cả hai đúng | Chỉ Text-only đúng | Chỉ Multimodal đúng | Cả hai sai |
| --- | ---: | ---: | ---: | ---: |
| Fake | 8 | 4 | 2 | 3 |
| Real | 14 | 1 | 0 | 1 |
| **Tổng** | **22** | **5** | **2** | **4** |

Hai cấu hình bất đồng ở 7/33 mẫu. Cả hai ca chỉ Multimodal đúng có nhãn
nguồn fake. Phân tích theo chất lượng ảnh, sự kiện hoặc nhà xuất bản chờ
metadata #47 được DATA duyệt. `fake_score` là điểm phân loại theo nhãn nguồn,
chưa hiệu chuẩn thành xác suất. Kiểm chứng sự thật và phát hiện ảnh chỉnh
sửa cần quy trình và bằng chứng riêng. [Phương pháp #47](error-analysis.md)

## Demo, hiệu năng và truy vết yêu cầu

Bản đóng gói mở popup từ tab hiện tại, tự trích xuất nội dung, tự chọn ảnh
và gửi multipart khi bấm Phân tích. API v0.2.0 chạy loopback. Kết quả hiển
thị nhãn và điểm, kèm model version, thời gian và chi tiết khi mở. Luồng
sửa/dán văn bản và chọn/tải ảnh trong thiết kế chưa đi qua popup đóng gói.
[Đối chiếu demo #43](e2e-real-model.md) · [Rà quyền, CORS và riêng tư #44](security-privacy-review.md)

QA đo bản Multimodal `multimodal-20261126-105d5f14e79a` trên Windows 11,
CPU 16 luồng logic, Python 3.13.17 và CLIP offline. Backend trả kết quả hợp lệ
cho cả 21 yêu cầu tổng hợp. Với 20 yêu cầu sau warm-up, median là **101 ms
ở server và 111,01 ms HTTP**. Harness đo được working set đỉnh lấy mẫu
771,04 MiB. Windows chưa cung cấp số RAM vật lý lắp đặt trong lượt đo.
Bundle giữ trạng thái `candidate` theo #49 và được xác minh riêng bằng
freeze đã ký. Cần Backend review và đo trên máy bàn giao. [JSON QA](qa-benchmark-signed-bundle.json) ·
[Báo cáo #52](performance.md)

PR #121 ghi nhận 4/10 bài trích xuất thành công trong khảo sát riêng. Mục tiêu
của dự án là ít nhất 8/10 trên bộ trang nghiệm thu. Cần kiểm bằng đúng gói
bàn giao và bộ trang được duyệt. [Khảo sát PR #121](https://github.com/ngnsusinn/anti-fake-news/pull/121) ·
[Kế hoạch QA](../docs/test-plan.md)

| Yêu cầu | Ca | Trạng thái và bằng chứng |
| --- | --- | --- |
| F01 · Tab nguồn | T01 | Popup lấy tab active. Chờ diễn tập nhiều tab cùng gói. [#43](e2e-real-model.md) |
| F02 · Trích/sửa/dán | T02 | Trích xuất có trong popup. Sửa/dán chờ chốt UI. [#43](e2e-real-model.md) |
| F03 · Chọn ảnh | T03 | Tự chọn ảnh. Chọn/tải tay chờ chốt UI. [#43](e2e-real-model.md) |
| F04 · Kiểm đầu vào | T04–T05 | Có bằng chứng API v0.2.0 trên fixture. Còn xác nhận hành vi bản demo. [#28](api-contract-results.md) |
| F05 · Gọi API | T06 | Unit xác nhận multipart và UUID. Chờ cùng bản demo. [#43](e2e-real-model.md) |
| F06 · Kết quả | T07 | UI có các trường. Chờ kiểm model version trên gói thật. [#43](e2e-real-model.md) |
| F07 · Phục hồi | T08–T09 | Unit xác nhận lỗi và vòng đời. Giữ input và lỗi runtime cần diễn tập. [#43](e2e-real-model.md) |
| F08 · Thực nghiệm | T10–T11 | Có audit Train/Val, freeze đã ký và audit 33/33 Test đạt. Chờ ML review. [#29](leakage-audit.md) · [#58](evaluation-audit.md) |
| NFR · Trích xuất, tốc độ và riêng tư | T12 | Benchmark QA cùng bundle đạt mục tiêu tốc độ. Chờ bộ 10 trang, đo trên máy bàn giao và kiểm quyền/CORS. [#44](security-privacy-review.md) · [#52](performance.md) |

Các mã F01–F08 trong DEFINE tương ứng FR-01–FR-08 trong backlog.
[Ma trận gốc](../docs/test-plan.md) · [Thiết kế](../DESIGN.md) · [Sơ đồ](../DIAGRAMS.md)

## Điều kiện ký báo cáo

DATA xác nhận quyền chia sẻ và chỉ mục #48. ML review audit #58,
Integration đồng bộ kết quả ở #51 và xuất bằng chứng #47 nếu có metadata.
Backend xác nhận benchmark #52 trên máy demo. QA đối chiếu lại phiên bản và
ma trận sau buổi diễn tập, rồi chuyển ML review. [Chỉ mục bàn giao](../release/release-index.json)
