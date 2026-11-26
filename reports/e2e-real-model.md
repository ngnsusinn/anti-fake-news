# AFN-043 · End-to-end Extension → FastAPI → mô hình

**26/11/2026 · BLOCKED.** QA `dangnguyen0512`, reviewer DATA `locnguyen230`.
Mã đã rà: [`aefb0ef`](https://github.com/ngnsusinn/anti-fake-news/commit/aefb0efc2b18fbb3a06d1766d1471ec188933eaf).
Bản cần nghiệm thu: API v0.2.0, Extension unpacked 0.1.0 và
`afn-multimodal` / `multimodal-20261126-105d5f14e79a` theo [hồ sơ #49](pre-test-signoff.md).

| Ca | Trạng thái của bản đóng gói | Bằng chứng / phần cần chạy |
| --- | --- | --- |
| T01 · Đúng tab | Đã đọc mã | Popup lấy tab active khi bấm Phân tích. Chạy hai tab có tiêu đề/ảnh khác nhau để kiểm tra dữ liệu và kết quả. |
| T02 · Trích xuất và sửa | Một phần | Popup có tự trích xuất. Bản đóng gói thiếu sửa văn bản và nhập thủ công. |
| T03 · Chọn một ảnh | Một phần | Popup tự chọn ảnh hợp lệ đầu tiên. Bản đóng gói thiếu bộ chọn ảnh và tải tệp. |
| T04 · Giới hạn nhập | Một phần | [API #28](api-contract-results.md) có bằng chứng 400/413. Popup cắt nội dung theo giới hạn, cần đối chiếu UX với tiêu chí giữ bản nhập. |
| T05 · Kiểm tra ảnh | Bằng chứng Backend | [Kiểm thử #28](api-contract-results.md) có MIME, byte, ảnh hỏng và EXIF. |
| T06 · Gửi tường minh | Unit đạt | API client gửi multipart sau thao tác, UUID và đúng một ảnh. Chờ ghi bằng chứng HTTP đã ẩn dữ liệu cùng bản demo. |
| T07 · Kết quả mô hình | Chờ chạy | Cần thấy nhãn, điểm, model ID/version, thời gian, UUID và trạng thái cắt text từ bundle ghim. |
| T08 · Lỗi và thử lại | Unit đạt, UI thật chưa chạy | Có test timeout và nhánh 401/503. Cần dừng Backend, thử lại, xác minh giữ dữ liệu với luồng nhập chỉnh sửa. |
| T09 · Phản hồi cũ | Unit đạt | Lifecycle loại kết quả cũ; cần chạy lại race và nhiều tab trên bản demo. |

`manifest.json` trỏ vào `popup.html`. Danh sách đóng gói trong
[`package_extension.py`](../scripts/package_extension.py) bỏ `analyze.html`
và service worker của luồng nhập tay. File còn trong mã nguồn và báo cáo
[UX #55](ux-review.md) mô tả luồng cũ. Extension `ngnsusinn` và Integration
`fulord26` cần xác nhận phạm vi UI áp dụng cho #43, rồi bàn giao gói và test
cập nhật. Các ca T02/T03/T08 giữ trạng thái một phần đến khi có bằng chứng
hoặc tiêu chí được hai bên cập nhật.

## Chạy và lưu bằng chứng

1. Bundle đã qua kiểm hash và nạp bằng loader theo [audit #58](evaluation-audit.md).
   Cache CLIP và hai tệp Train/Val đã được đối chiếu hash. `ml.freeze verify`
   trên hồ sơ nháp đã đạt. Khi diễn tập, đối chiếu metadata SHA-256
   `6cd766a982015fb661f7eee8a5aa1317f05efc562769f8a13ba054e572fc09d5`
   và model version. Giải quyết yêu cầu trạng thái bundle `candidate`/ `frozen`
   giữa [biên bản #49](pre-test-signoff.md) và [checklist gói #54](../release/backend-checklist.md).
2. Đóng gói và nạp Extension theo [hướng dẫn](../docs/extension-setup.md), đặt
   đúng origin và token demo cục bộ. Khởi động Backend real rồi ghi HTTP 200,
   `model_ready=true`, mode real và commit của hai phần.
3. Gán `AFN_REAL_TEST_TOKEN` trong môi trường riêng, rồi chạy
   `python scripts/test_extension_smoke.py --real-endpoint http://127.0.0.1:8000`.
   Runner dùng trang tổng hợp để xác minh đường kỹ thuật. Kiểm model version
   trong mục chi tiết và chỉ lưu mã HTTP, UUID, phiên bản, trường metric kỹ thuật
   và ảnh chụp đã làm sạch.
4. Dùng bài tiếng Anh và ảnh được phép, chọn trước ngoài Test, chạy các ca UI,
   dừng Backend và thử lại sau khi khởi động. Ghi kết quả thao tác, phiên bản,
   người chạy và thời điểm. Chạy ca 503 riêng ở demo real thiếu bundle. Với
   production, thiếu bundle phải dừng khởi động.

Lượt này Node **12/12** trên API client, phục hồi lỗi, lifecycle và result view.
Smoke Backend production offline dùng cache CLIP ghim và bundle nghiên cứu.
Health 200 real/ready, thiếu token 401 và predict 200 với
`afn-multimodal` / `multimodal-20261126-105d5f14e79a` trên đầu vào tổng hợp.
Chromium và các ca demo thủ công chưa chạy trong lượt này. Bằng chứng
tích hợp [#39](backend-integration.md) dùng bản ứng viên trước, cùng
[ma trận #45](regression-matrix.md) làm tài liệu tham chiếu.
