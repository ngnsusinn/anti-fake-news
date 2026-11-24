# Kế hoạch và ma trận kiểm thử QA — AFN-014

Cập nhật: 23/11/2026. **Đây là kế hoạch kiểm thử, chưa phải kết quả chạy đạt.** Ánh xạ F01–F08 theo `DEFINE.md` (tương ứng cách gọi FR-01–FR-08 trong issue). Bản `DESIGN.md` hiện chưa chứa định nghĩa chi tiết T01–T12, vì vậy mã ca bên dưới do QA đề xuất, cần nhóm xác nhận.

## 1. Ma trận T01–T12

| Ca | Yêu cầu | Người/issue triển khai | Bước kiểm thử / đầu vào | Kết quả mong đợi | Bằng chứng cần lưu |
| --- | --- | --- | --- | --- | --- |
| T01 | F01 | EXTENSION #10 | Bấm extension tại bài A, sau đó chuyển sang tab B | Phiên gắn đúng tab và URL; dữ liệu không lẫn giữa tab | Ảnh chụp, nhật ký phiên đã ẩn nội dung |
| T02 | F02 | EXTENSION #11 | Mở bài thường, DOM rỗng/động, ảnh có URL tương đối | Lấy đúng tiêu đề/nội dung và URL ảnh tuyệt đối; có đường nhập thủ công | Đối chiếu trích xuất trên bộ 10 trang |
| T03 | F03 | EXTENSION #25 | Chọn một trong nhiều ảnh hoặc tải PNG tự tạo | Hiển thị đúng ảnh xem trước; chỉ gửi một ảnh đã xác nhận | Ảnh chụp và metadata request |
| T04 | F04 | EXTENSION #26, BACKEND #22–23 | Gửi text rỗng/chỉ khoảng trắng, >50.000 ký tự hoặc title >500 | Từ chối đầu vào, không dự đoán; giữ dữ liệu người dùng | Thông báo giao diện, lỗi 400 đã làm sạch |
| T05 | F04 | BACKEND #22–23 | Gửi byte ảnh hỏng, MIME sai, ảnh >10 MiB, JPEG có EXIF xoay | API thật từ chối ảnh lỗi/MIME sai, trả 413 khi quá lớn; xử lý hướng ảnh theo hợp đồng đã chốt | Mã lỗi, bằng chứng giải mã |
| T06 | F05 | EXTENSION #27, BACKEND #22 | Quan sát mạng trước/sau khi bấm “Phân tích” | Chỉ POST sau thao tác; multipart gồm UUID, title tùy chọn, text và một image | Bản ghi request đã ẩn dữ liệu riêng |
| T07 | F06 | BACKEND #37, EXTENSION #40 | Dùng mô hình thật với fixture hợp lệ | Có nhãn fake/real, điểm 0–1, định danh/phiên bản mô hình thật và thời gian xử lý | Response thật và hash artifact |
| T08 | F07 | EXTENSION #41, BACKEND #38 | Tắt API, gây timeout/lỗi mạng/CORS rồi thử lại | Thông báo dễ hiểu, giữ bản nhập, không tạo kết quả giả hoặc tự retry nguy hiểm | Ảnh chụp, status và trạng thái server |
| T09 | F07 | EXTENSION #42 | Gửi A rồi B trong cùng tab, cho A trả về trễ hơn B | Bỏ kết quả A đã cũ, chỉ hiển thị B; tab khác không bị ảnh hưởng | UUID và thứ tự sự kiện |
| T10 | F08 | DATA #18, ML #34 | Kiểm tra manifest, nhóm, chia 70/15/15 và seed | Không rò rỉ nhóm; ba mô hình dùng cùng chia tập; không xem Test để chọn tham số | Hash manifest/split, báo cáo audit |
| T11 | F08 | ML #34/#49/#50; QA #58 | Chọn C/ngưỡng chỉ trên Validation; tại #49 ML+QA ký hash và protocol trước khi mở Test; #50 xuất predictions/metrics; #58 audit lại từ predictions | Test chỉ chạy sau sign-off #49; #58 kiểm hash và tái tính metric **sau #50**, không tuning hoặc inference lại | `model-freeze.json`, `pre-test-signoff.md`, predictions, `evaluation-audit.md` |
| T12 | NFR, F01–F08 | QA #43, INTEGRATION #45, BACKEND #52 | Chạy end-to-end trên 10 trang đã chọn; đo ≥20 lần suy luận thật trên máy demo | Báo tỷ lệ trích xuất và trung vị thời gian thực tế, so với mục tiêu trong DEFINE | Checklist trang, CSV thời gian, cấu hình máy |

## 2. Chỉ tiêu phi chức năng

- Trích xuất đúng ít nhất **8/10 trang** trong bộ nghiệm thu đã chọn trước.
- Trung vị suy luận sau nạp mô hình **dưới 10 giây**, đo tối thiểu **20 lần** trên máy demo; ghi CPU/RAM và phiên bản.
- Không suy ra chất lượng mô hình thật từ kết quả mock.

## 3. Fixture và phân tách dữ liệu

- Fixture tổng hợp do QA quản lý: `tests/fixtures/qa/v0.1.1/`, có [hướng dẫn nguồn gốc](../tests/fixtures/README.md).
- Registry `manifest.json` nêu nguồn gốc và version của từng mẫu; `session-race.json` và `split-policy.json` giúp bàn giao rõ phiên và chính sách split. Bộ sinh fixture có text 50.001 ký tự, title 501 ký tự, ảnh hỏng, sai MIME, PNG hợp lệ vượt 10 MiB và EXIF tùy chọn.
- Fixture API hiện có của Backend: `backend/tests/fixtures/api/v0.1.1/`, chỉ dùng phát triển hợp đồng/mock, **không** phải Test nghiên cứu hoặc bằng chứng suy luận thật.
- **Train** dùng để fit; **Validation** dùng chọn siêu tham số/ngưỡng; **Test** giữ kín đến sau khi đóng băng và không dùng sửa giao diện, chọn mô hình, benchmark hoặc thử đi thử lại để tuning.
- QA chỉ audit **metadata** Test trước thời điểm khóa: số lượng, hash, trùng nhóm; không dùng nội dung/nhãn/dự đoán Test để tối ưu. **QA kiểm hash và ký cùng #49 trước #50**, còn **#58 chỉ đối chiếu predictions, hash và tái tính metrics sau khi #50 hoàn thành**. Đây là hai hoạt động kiểm tra khác nhau, không được tạo phụ thuộc vòng.

## 4. Kiểm thử lỗi và cách ghi kết quả

- Với race: dùng UUID riêng cho request A/B, ghi thứ tự gửi/trả về; client phải bỏ phản hồi cũ.
- Với timeout: kiểm tra vẫn giữ bản nhập; việc client hủy request không bảo đảm công việc server đã dừng.
- Với CORS: thử origin không được phép, tách riêng phép thử xác thực token vì CORS **không** phải cơ chế xác thực.
- Mỗi lần chạy lưu: `ca | commit SHA | phiên bản fixture | môi trường | mong đợi | thực tế | PASS/FAIL/BLOCKED | URL evidence | người chạy | ngày`.
- Kiểm tra độc lập registry bằng `python -m unittest discover -s tests/fixtures/qa -p "test_*.py" -v`; kết quả này là kiểm tra fixture, **không** thay thế chạy T01–T12 trên hệ thống thật.

## 5. Phụ thuộc trước nghiệm thu

Contract [v0.1.1](api-contract.md) còn **đề xuất**, chờ Backend/ML/Extension phê duyệt (#8). Auth, giới hạn truyền thực, giải mã ảnh, CORS, suy luận mô hình thật thuộc #22/#23/#38/#37. Không đánh dấu T04–T08 PASS chỉ vì mock hoạt động. T10–T12 chờ split nhóm, CLIP CPU và artifact thật. Phiếu đăng ký đề tài xác định bài viết tiếng Anh. Bản sửa dòng phạm vi trong DEFINE và giao thức thực nghiệm nằm tại [PR #68](https://github.com/ngnsusinn/anti-fake-news/pull/68).

Người phụ trách QA: `dangnguyen0512`; reviewer chuyên môn DATA: `locnguyen230`; CODEOWNER: `ngnsusinn`.
