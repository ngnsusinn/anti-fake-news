# Danh mục dữ liệu kiểm thử QA — AFN-014

Chỉ lưu **dữ liệu giả lập tự tạo** phục vụ kiểm thử hợp đồng. Không đưa secret, bài báo/ảnh thu thập chưa rõ quyền, dữ liệu Test nghiên cứu, trọng số mô hình hoặc thông tin máy cá nhân lên GitHub.

| Namespace / tệp | Nguồn gốc | Mục đích | Kết quả dự kiến |
| --- | --- | --- | --- |
| `qa/v0.1.1/empty-text.json` | QA tự tạo, 23/11/2026 | T04: phần thân chỉ có khoảng trắng | Từ chối `invalid_input` khi API thật đã xác thực |
| `qa/v0.1.1/request-valid-fields.json` | QA tự tạo, 23/11/2026 | T06: mẫu cấu trúc trường multipart | Gửi UUID + văn bản + một ảnh hợp lệ; **không** gửi nguyên JSON vào `/predict` |
| `backend/tests/fixtures/api/v0.1.1/` | Fixture phát triển của Backend có sẵn | Kiểm thử schema/parser/mock | Không chứng minh mô hình suy luận thật |

Các tệp QA bổ sung trong `qa/v0.1.1/`:

- `manifest.json`: danh mục có version, tác giả/nguồn và mục đích của từng fixture.
- `session-race.json`: hai request UUID, thứ tự phản hồi đảo ngược để thử phiên/tab (T01, T09).
- `split-policy.json`: quy tắc chia Train/Validation/Test để audit **metadata**, không chứa bất kỳ mẫu Test nghiên cứu nào (T10, T11).
- `generate_fixtures.py`: sinh ảnh PNG hợp lệ, byte ảnh hỏng, MIME giả, PNG hợp lệ >10 MiB, text 50.001 ký tự và tiêu đề 501 ký tự. Có thể sinh JPEG EXIF orientation=6 nếu đã cài riêng Pillow.

## Chạy thử bộ fixture

Từ thư mục gốc repository:

```bash
python -m unittest discover -s tests/fixtures/qa -p "test_*.py" -v
python tests/fixtures/qa/generate_fixtures.py
# Tùy chọn: cài Pillow trong môi trường QA rồi chạy
python tests/fixtures/qa/generate_fixtures.py --with-exif
```

Lệnh sinh dữ liệu mặc định tạo **thư mục tạm mới** và in đường dẫn. Không commit các tệp nhị phân đã sinh. Các bài kiểm thử `unittest` chỉ xác nhận cấu trúc/nguồn gốc/boundary của fixture; **không** gửi API, không chứng minh endpoint hay mô hình đạt yêu cầu.

## Cách tạo các fixture khác tại máy cục bộ

1. **Văn bản dài:** tạo chuỗi `"a".repeat(50001)` để thử giới hạn 50.000 Unicode code point; thử title dài 501 ký tự. Không cần bài báo thật.
2. **Ảnh hỏng và MIME sai:** tạo tệp `.png` chứa nội dung `not-an-image`, lần lượt thử MIME `image/png` và `text/plain`. Mock hiện tại **không** thay thế kiểm tra giải mã ảnh thật của #23.
3. **Ảnh quá lớn:** tạo buffer >10 MiB trong thư mục tạm, không commit. API thật dự kiến trả 413; giới hạn tổng request 12 MiB còn là đề xuất.
4. **Ảnh EXIF:** dùng JPEG tự tạo hoặc ảnh được phép chia sẻ có EXIF orientation=6; ghi tác giả/quyền sử dụng và kích thước kỳ vọng sau xoay. Chưa bổ sung ảnh vào Git nếu chưa xác minh nguồn.
5. **Race/timeout/CORS:** tạo hai UUID khác nhau, cố ý đảo thứ tự phản hồi, ngắt/trì hoãn server và thử origin không hợp lệ. Chỉ lưu trace đã xóa nội dung nhạy cảm.

## Quy tắc phân tách

- Fixture phát triển và **Test nghiên cứu** phải nằm ở các namespace/bộ dữ liệu tách biệt.
- Không dùng Test nghiên cứu để chỉnh UI, benchmark, chọn C/ngưỡng hay cấu hình.
- Khi thay đổi hợp đồng phải cập nhật phiên bản fixture, test plan và báo Backend/ML/Extension; không âm thầm đổi tên trường.
- Các JSON hiện có chỉ là **bản mẫu đầu vào**, chưa phải báo cáo kiểm thử PASS.
