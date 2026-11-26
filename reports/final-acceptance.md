# AFN-060 · Nghiệm thu trên máy sạch và bàn giao

**26/11/2026 · BLOCKED.** QA `dangnguyen0512`, reviewer ML `0xDa1Vu`.
Bản chuẩn bị từ [`aefb0ef`](https://github.com/ngnsusinn/anti-fake-news/commit/aefb0efc2b18fbb3a06d1766d1471ec188933eaf).
[Chỉ mục phiên bản và đầu vào](../release/release-index.json)

## Checklist cho thành viên chạy độc lập

| Mục | Tiêu chí/bằng chứng cần lưu | Trạng thái |
| --- | --- | --- |
| Tạo môi trường sạch | Dùng checkout/gói cùng commit, giải nén ZIP và cài hai bộ pin Python 3.13 từ wheelhouse theo #54. Lưu phiên bản OS/CPU/RAM, Python/Chromium, commit, ZIP SHA-256 và kết quả `pip check`. | Chưa chạy trên máy sạch. |
| Xác minh artifact | Xác minh metadata, các mảng bundle và CLIP cache theo #49/#54. Giải quyết khác biệt `candidate`/ `frozen` trước khi chốt hash. Ghi SHA và model ID/version. | ML đã ký hồ sơ, còn bàn giao/xác minh QA. |
| Khởi động | Tạo token cục bộ và đặt đúng origin của extension unpacked. Chạy Backend bằng `python -m app` ở loopback. Kiểm real, ready, contract và version. | Chưa chạy bộ đóng gói cuối. |
| Demo thật và lỗi | Chạy [#43](e2e-real-model.md) từ tab có bài/ảnh được phép ngoài Test. Lưu kết quả T01–T09, lỗi 401/503, dừng/restart Backend, phục hồi và version model. Kiểm [#44](security-privacy-review.md). | Chờ gói #57, tiêu chí UI và bundle. |
| Nghiên cứu và hiệu năng | Đối chiếu Test IDs/hashes/metrics từ audit #58, dữ liệu #48, báo cáo #59 và benchmark #52 trên cùng bundle. Kiểm bộ 10 trang và median sau warm-up. | Chờ #50/#58, benchmark đúng phiên bản và review. |
| Bàn giao | Người chạy độc lập ghi tên, ngày và kết quả. QA/ML đối chiếu hash, quyền phân phối, và trạng thái Project. Chỉ chuyển Done khi đủ bằng chứng và review. | Chưa ký. |

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

- ML `0xDa1Vu` và QA `dangnguyen0512`: bàn giao và kiểm bundle/hashes cùng bản
  #49, ký freeze, bàn giao Test #50 và audit #58. [Biên bản](pre-test-signoff.md)
- Backend `Phuc1232`, Integration `fulord26` và Extension `ngnsusinn`: thống
  nhất trạng thái artifact mà gói chấp nhận, chạy #54/#57 trên máy đích và
  chốt các ca chỉnh sửa/nhập tay trong bản tích hợp.
- DATA `locnguyen230` và QA: xác nhận dữ liệu được phép bàn giao, bộ trang
  nghiệm thu ngoài Test và bằng chứng riêng tư.
- QA và ML: chốt [báo cáo #59](final-report.md) sau khi có #48/#51/#52/#58. Hai bên ký sau khi thành viên độc lập hoàn tất checklist.
