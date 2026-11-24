# Quy ước làm việc nhóm — AFN-013 (bản nháp chờ thống nhất)

Cập nhật: 23/11/2026. Phạm vi: 60 công việc AFN-001 đến AFN-060 trong 4 tuần. Theo xác nhận của đại diện QA ngày 23/11/2026, **cả nhóm đã thống nhất** giờ review 11:30, 20:30 hằng ngày và checkpoint 20:30 tại bốn ngày cuối tuần dưới đây. QA đã lựa chọn **ngày khóa Test 13/12/2026**; giờ khóa cụ thể chưa được cung cấp và việc thực hiện phụ thuộc vào các điều kiện đóng băng/kiểm tra dữ liệu.

## 1. Phân công trách nhiệm

Đã đối chiếu người được giao trên GitHub ngày 23/11/2026:

| Vai trò | Tài khoản GitHub thật | Issue phụ trách | Số lượng |
| --- | --- | --- | ---: |
| Dữ liệu (DATA) | `locnguyen230` | #2, #3, #16–18, #31–32, #46–48 | 10 |
| Học máy (ML) | `0xDa1Vu` | #5, #6, #19–21, #34–36, #49–50 | 10 |
| Backend | `Phuc1232` | #7–9, #22–23, #37–39, #52–53 | 10 |
| Tiện ích trình duyệt (EXTENSION) | `ngnsusinn` | #10–11, #25–27, #41–42, #55–57 | 10 |
| Kiểm thử (QA) | `dangnguyen0512` | #13–15, #28–29, #43–44, #58–60 | 10 |
| Tích hợp và nghiên cứu (INTEGRATION) | `fulord26` | #1, #4, #12, #24, #30, #33, #40, #45, #51, #54 | 10 |

Mỗi issue có **một người chịu trách nhiệm chính**. Người review theo chuyên môn lấy theo mô tả từng issue: QA được DATA review; DATA được QA review; ML được BACKEND review; BACKEND được ML review; EXTENSION được QA review; INTEGRATION theo vai trò được ghi trong issue. Ngoài ra, `@ngnsusinn` vẫn là **CODEOWNER bắt buộc** của toàn bộ tệp theo `.github/CODEOWNERS`. Review chuyên môn không thay thế phê duyệt của CODEOWNER.

## 2. Bốn giai đoạn và bảng theo dõi

| Tuần | Khoảng thời gian (giờ Việt Nam) | Mục tiêu |
| --- | --- | --- |
| 1 | 17–23/11/2026 | Chốt phạm vi, hợp đồng, khả thi dữ liệu và môi trường |
| 2 | 24–30/11/2026 | Xây dựng và thử nghiệm các thành phần |
| 3 | 01–07/12/2026 | Tích hợp, sửa lỗi, chạy luồng thực |
| 4 | 08–14/12/2026 | Khóa mô hình, kiểm thử cuối, báo cáo, bàn giao |

Trước khi có GitHub Project, dùng **GitHub Issues làm bảng theo dõi tương đương**: lọc `label:week:1` đến `label:week:4`, `assignee:<tài khoản>`, `label:area:qa` và milestone. Không coi đó là bằng chứng một GitHub Project tùy chỉnh đã được tạo.

Các trường nên cấu hình khi tạo Project: **Iteration** (tuần), **Status** (trạng thái), **Priority** (ưu tiên), **Estimate** (giờ ước lượng), **Area** (bộ phận). Giá trị Estimate lấy từ từng issue; không tự suy đoán. Tạo view theo tuần và theo thành viên.

Luồng trạng thái đề xuất: **Backlog → Ready → In progress → Review → Done**; dùng **Blocked** khi thiếu điều kiện. Khi chưa có Project, ghi rõ trạng thái trong issue/PR; trạng thái Closed đơn thuần không chứng minh đã nghiệm thu, nhất là các issue có cảnh báo “CẦN KIỂM TRA LẠI”.

## 3. Định nghĩa Ready và Done

- **Ready (sẵn sàng bắt đầu):** có owner, đầu ra và tiêu chí nghiệm thu rõ ràng; đã kiểm tra phụ thuộc để **bắt đầu**; xác định phiên bản hợp đồng dùng chung. Có thể làm phần độc lập trước khi đủ điều kiện nghiệm thu cuối.
- **Review (chờ duyệt):** có PR/commit, hướng dẫn chạy, kết quả kiểm tra thực tế, tình huống lỗi, xuất xứ fixture, các giao diện bị ảnh hưởng và reviewer cụ thể.
- **Done (hoàn thành):** có toàn bộ đầu ra; các tiêu chí nghiệm thu được kiểm chứng; kiểm thử có bằng chứng; không còn blocker cản nghiệm thu; có review chuyên môn và CODEOWNERS theo quy định.
- Không dùng kết quả mock để chứng minh suy luận thật; không thay Test bằng dữ liệu phát triển; không tự đánh dấu Done khi còn phụ thuộc chưa đạt.

## 4. Quy trình review và bàn giao

1. Người thực hiện mở PR gắn issue, mô tả phạm vi, phiên bản API/fixture, lệnh kiểm thử và kết quả. Người review chuyên môn kiểm tra trước khi CODEOWNER phê duyệt/merge.
2. Hai khung giờ review **đã được nhóm thống nhất (theo xác nhận của QA)**: **11:30** và **20:30 hằng ngày** theo `Asia/Ho_Chi_Minh`, áp dụng trong cả bốn tuần.
3. Khi thay đổi hợp đồng/API, thông báo các bên dùng giao diện (Backend, ML, Extension, QA), nâng phiên bản khi cần và sửa fixture/tài liệu liên quan cùng lúc.
4. Ghi blocker theo mẫu: `issue | vấn đề | đầu vào/phiên bản còn thiếu | người gỡ | hành động | hạn dự kiến | liên kết bằng chứng | trạng thái`. Người bị chặn chuyển sang việc độc lập, không làm giả dữ liệu.
5. Quy tắc sử dụng quỹ dự phòng **đề xuất**: ưu tiên blocker P0, tiếp đến lỗi tích hợp/hồi quy, sau cùng mới là chỉnh sửa tài liệu. Ghi số giờ dùng, người phê duyệt và phạm vi phải giảm; không tự tăng lịch hoặc đổi kiến trúc.
6. Các checkpoint **đã được nhóm thống nhất (theo xác nhận của QA)**, đều bắt đầu lúc **20:30, giờ Việt Nam**: **23/11/2026 (W1)**, **30/11/2026 (W2)**, **07/12/2026 (W3)** và **14/12/2026 (W4)**. Mỗi checkpoint rà bằng chứng và quyết định **Go / Conditional Go / No Go**. **Trình tự bắt buộc:** (1) #49 đóng băng mô hình, tiền xử lý, ngưỡng, dữ liệu/split và lưu hash; QA cùng ML đối chiếu hash, timestamp, protocol và ký `reports/pre-test-signoff.md` **trước khi** mở Test; (2) #50 chỉ chạy Test sau khi #49 được ký hợp lệ, lưu predictions/metrics; (3) #58 **sau #50** kiểm tra hash so với freeze và tái tính metrics từ predictions đã lưu. Không lấy hoàn thành #58 làm điều kiện trước #50. **Ngày khóa Test được QA chọn: 13/12/2026 (giờ Việt Nam); chưa chốt giờ cụ thể.** Nếu #49 chưa được ký và QA chưa xác nhận hash, không được mở Test chỉ vì đã đến ngày này; ghi blocker và xin nhóm quyết định lịch điều chỉnh. #58 chỉ nghiệm thu sau khi #50 đã bàn giao dự đoán.

## 5. Quyết định còn chờ nhóm

- **Đã chốt lịch review/checkpoint theo xác nhận của QA.** QA đã chọn ngày khóa Test **13/12/2026**; cần nhóm xác nhận ngày này, thống nhất giờ khóa và kiểm tra điều kiện #49 cùng xác nhận hash của QA trước khi thực hiện; #58 audit sau #50.
- Giải quyết mâu thuẫn ngôn ngữ: `DEFINE.md` mô tả tiếng Việt, nhưng bản hợp đồng API đề xuất từng nêu tiền xử lý tiếng Anh.
- Duyệt hợp đồng API/Predictor v0.1.1: byte ảnh hoặc RGB, EXIF, giới hạn request 12 MiB, timeout, token, ưu tiên lỗi và phần form trùng lặp.
- `DESIGN.md` hiện có §1–4, nên những tham chiếu §8–14 trong issue chưa thể đối chiếu với bản hiện tại.

Tham chiếu: [DEFINE](../DEFINE.md), [DESIGN](../DESIGN.md), [hợp đồng API](api-contract.md), [Issue #13](https://github.com/ngnsusinn/anti-fake-news/issues/13), [CODEOWNERS](../.github/CODEOWNERS).
