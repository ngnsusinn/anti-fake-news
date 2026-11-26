# AFN-060 · Nghiệm thu trên máy sạch và bàn giao

**26/11/2026 · BLOCKED.** QA `dangnguyen0512`, reviewer ML `0xDa1Vu`.
Bản chuẩn bị từ [`4175c97`](https://github.com/ngnsusinn/anti-fake-news/commit/4175c974e69d9364aff4428aade3acb7e39f4824).
[Chỉ mục phiên bản và đầu vào](../release/release-index.json)

## Checklist cho thành viên chạy độc lập

| Mục | Tiêu chí/bằng chứng cần lưu | Trạng thái |
| --- | --- | --- |
| Tạo môi trường sạch | Dùng checkout/gói cùng commit, giải nén ZIP và cài hai bộ pin Python 3.13 từ wheelhouse theo #54. Lưu phiên bản OS/CPU/RAM, Python/Chromium, commit, ZIP SHA-256 và kết quả `pip check`. | Đã đóng gói và giải nén sạch ZIP nguồn 23 tệp. Vẫn dùng runtime QA sẵn có. Chờ một thành viên khác cài wheelhouse và chạy trên máy bàn giao. |
| Xác minh artifact | Xác minh metadata, các mảng bundle và CLIP cache theo #49/#54. Giải quyết khác biệt `candidate`/ `frozen` trước khi chốt hash. Ghi SHA và model ID/version. | Freeze hai chữ ký và các bundle đã verify. CLIP cache đã ghim hash. Chờ xác minh lại trên máy bàn giao. |
| Khởi động | Tạo token cục bộ và đặt đúng origin của extension unpacked. Chạy Backend bằng `python -m app` ở loopback. Kiểm real, ready, contract và version. | Production smoke từ ZIP giải nén đạt 200 real/ready, 401 thiếu token và 200 đúng model version khi gửi hợp lệ. Qua bộ launcher trên máy bàn giao còn chờ. |
| Demo thật và lỗi | Chạy [#43](e2e-real-model.md) từ tab có bài/ảnh được phép ngoài Test. Lưu kết quả T01–T09, lỗi 401/503, dừng/restart Backend, phục hồi và version model. Kiểm [#44](security-privacy-review.md). | Chờ gói #57, tiêu chí UI và diễn tập với bundle đã xác minh. |
| Nghiên cứu và hiệu năng | Đối chiếu Test IDs/hashes/metrics từ audit #58, dữ liệu #48, báo cáo #59 và benchmark #52 trên cùng bundle. Kiểm bộ 10 trang và median sau warm-up. | Audit từ predictions #50 đạt 33/33 ID và khớp metrics. Benchmark phía server median 101 ms trên máy QA. Chờ #59 review, bộ 10 trang và phép đo máy đích. |
| Bàn giao | Người chạy độc lập ghi tên, ngày và kết quả. QA/ML đối chiếu hash, quyền phân phối, và trạng thái Project. Chỉ chuyển Done khi đủ bằng chứng và review. | Chưa ký. |

## Bằng chứng QA hiện có

- ZIP nguồn SHA-256
  `17fc8033ebfafe0008bacc765ff778f67026c71ad7e986c86680f2b3d271767c`.
  Kiểm inventory 23 tệp, template token rỗng và gói không chứa dữ liệu thô
  hoặc weights. Smoke sau giải nén dùng đúng bundle Multimodal và cache
  CLIP offline. Test HTTP dùng đầu vào tổng hợp.
- [Audit kết quả](evaluation-audit.md) và [dữ liệu benchmark QA](qa-benchmark-signed-bundle.json)
  theo đúng freeze hai chữ ký. Benchmark dùng production candidate opt-in,
  đã verify freeze riêng trước khi đo. Thông số RAM vật lý chưa lấy được
  trên môi trường QA.
- Bằng chứng đồng ý phát hành và diễn tập độc lập Extension → Backend →
  model trên máy bàn giao vẫn cần được người chạy và ML xác nhận.

## Khôi phục và bàn giao

Dừng Backend, giải nén lại gói Backend đã xác minh trong thư mục mới, dựng
môi trường từ pins và nạp lại cache CLIP/bundle bàn giao. Tạo cấu hình cục bộ
với token hiện hành, dựng lại Extension unpacked, ghi origin mới nếu ID thay
đổi rồi khởi động lại. Dùng các lệnh smoke trong [hướng dẫn Backend](../docs/backend-setup.md)
và [hướng dẫn Extension](../docs/extension-setup.md). Giữ log đã làm sạch và
hash trong chỉ mục. Bàn giao source được duyệt cùng metadata và báo cáo,
qua kho riêng cho bundle và dữ liệu cần giới hạn truy cập. Kiểm quyền
trên ảnh và manifest trước khi chia sẻ dữ liệu.

## Blocker theo owner

- ML `0xDa1Vu` và QA `dangnguyen0512`: review kết quả audit #58 và báo cáo #59 cùng freeze đã ký. [Biên bản](pre-test-signoff.md)
- Backend `Phuc1232`, Integration `fulord26` và Extension `ngnsusinn`: thống
  nhất trạng thái artifact mà gói chấp nhận, chạy #54/#57 trên máy đích và
  chốt các ca chỉnh sửa/nhập tay trong bản tích hợp.
- DATA `locnguyen230` và QA: xác nhận dữ liệu được phép bàn giao, bộ trang
  nghiệm thu ngoài Test và bằng chứng riêng tư.
- QA và ML: chốt [báo cáo #59](final-report.md) sau khi có #48/#51/#52/#58. Hai bên ký sau khi thành viên độc lập hoàn tất checklist.
