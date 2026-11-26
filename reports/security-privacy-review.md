# AFN-044 · Rà quyền Extension, CORS, token và riêng tư

**26/11/2026 · PARTIAL, chờ nghiệm thu runtime và quyền phân phối.**
QA `dangnguyen0512`, reviewer DATA `locnguyen230`. Snapshot
[`aefb0ef`](https://github.com/ngnsusinn/anti-fake-news/commit/aefb0efc2b18fbb3a06d1766d1471ec188933eaf), API v0.2.0.

| Hạng mục | Kết quả rà | Bằng chứng / phần chờ |
| --- | --- | --- |
| Quyền MV3 | Đã rà mã | [Manifest](../extension/manifest.json) xin `activeTab`, `scripting`, HTTP loopback và host ảnh liệt kê. Wildcard tên miền phụ Reuters nằm trong host ảnh. Manifest không có `<all_urls>`, `storage` hoặc `web_accessible_resources`. Kiểm lại permissions trên gói demo. |
| DOM và ảnh | Đã rà mã | [Popup](../extension/popup.js) hiển thị chuỗi bằng `textContent`, ảnh qua object URL và dọn khi đóng. [Bộ đọc ảnh](../extension/modules/image-selection.js) kiểm JPEG/PNG, byte và pixel, bỏ cookie/referrer, chặn redirect và giới hạn ảnh loopback cùng origin nguồn. Fetch ảnh vẫn kết nối tới host nguồn. |
| Dữ liệu phiên | Đã rà mã | Gói hiện chạy popup, giữ bản đọc và tệp ảnh trong bộ nhớ. Luồng `service-worker.js`/session DTO cũ nằm ngoài [danh sách đóng gói](../scripts/package_extension.py). Rà lại DTO và quyền storage nếu luồng chỉnh sửa được đưa trở lại. |
| CORS | Đã rà cấu hình | [Middleware](../backend/app/cors.py) cho một origin Extension cấu hình chính xác, GET/POST, hai header yêu cầu và không bật credentials. Trống origin thì không cấp CORS. Chạy lại preflight đúng/sai origin trên gói demo. |
| Token và loopback | Đã rà mã và có bằng chứng API lịch sử | [Middleware request](../backend/app/validation.py) trả 401 cho token thiếu/sai/trùng. [Launcher](../backend/app/__main__.py) dùng Settings giới hạn loopback và tắt access log. [API client](../extension/modules/api-client.js) khóa HTTP `127.0.0.1`, bỏ cookie, từ chối redirect. `.env.example` để token trống. |
| Log và phát hành | Một phần | [Backend #53](backend-final-check.md) có bằng chứng lịch sử làm sạch lỗi startup. Token nằm trong cấu hình cục bộ của bản unpacked và người có quyền đọc gói có thể lấy được. Chỉ dùng để bảo vệ dịch vụ loopback trong demo. Chờ rà log cấu hình thực tế và inventory các gói cuối. |
| Dữ liệu được track | Cần DATA xác nhận | Cây Git có 286 tệp dưới `data/images/`, manifest xử lý và split JSON. Tại snapshot không thấy `.env`, runtime config, bundle weights trong thư mục artifact hoặc predictions Test cuối trong cây tệp. Kiểm kê theo đường dẫn, chưa quét toàn lịch sử hoặc xác nhận quyền phân phối từng tệp. DATA xác minh quyền theo [data card](../docs/data-card.md) trước khi đưa dữ liệu vào bàn giao. |

## Kiểm tra đã chạy và diễn tập cần làm

- Node **12/12** với `tests/frontend/{api-client,error-recovery,request-lifecycle,result-view}.test.mjs`,
  gồm chặn endpoint ngoài loopback, health không gửi token, ánh xạ lỗi và render bằng text.
- [QA API #28](api-contract-results.md) ghi kết quả 401 thiếu/sai token và
  503 khi chưa sẵn sàng ở commit trước. [CORS unit](../backend/tests/test_cors.py)
  và [config unit](../backend/tests/test_config.py) có ca preflight, token và
  giới hạn bind. Đã chạy `python -B -m pytest -q tests/test_cors.py tests/test_config.py tests/test_lifespan_logging.py`
  trong `backend/`. **38/38 PASS** trên Windows với Python 3.13.17. Smoke
  production loopback trả 401 khi thiếu token và 200 với token tạm cùng bundle
  ghim. Còn ca CORS với Extension đóng gói và rà quyền dữ liệu.
- Trên cùng gói demo, Backend `Phuc1232` và QA ghi origin quan sát được,
  mã HTTP và header CORS cho preflight hợp lệ và origin khác. Thử POST thiếu,
  sai và đúng token bằng đầu vào tổng hợp. Xác nhận địa chỉ listen loopback
  và chỉ lưu log đã ẩn token/nội dung/ảnh/đường dẫn cục bộ. Đối chiếu danh
  mục ZIP với checklist #54 và #57 trước review DATA.
