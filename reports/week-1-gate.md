# Báo cáo kiểm tra điều kiện cuối tuần 1 — AFN-015

**Thời điểm:** 23/11/2026, giờ Việt Nam.

**Quyết định sơ bộ: TIẾP TỤC CÓ ĐIỀU KIỆN — CHƯA KÝ NGHIỆM THU.** Các việc tuần 2 không bị phụ thuộc có thể bắt đầu; chưa đủ căn cứ đánh dấu checkpoint tuần 1 Done.

## 1. Kiểm tra đầu vào

| Điều kiện kiểm tra | Bằng chứng/trạng thái quan sát | Nhận định |
| --- | --- | --- |
| Pilot ≥30 URL và tỷ lệ khôi phục cả bài lẫn ảnh | [PR #66, recovery-pilot](https://github.com/ngnsusinn/anti-fake-news/blob/0b8402b192e9a235979804d162aba392b3e70d7d/reports/recovery-pilot.md): 400 đầu vào, 242 JSON, 217 body, 178 ảnh, **165 mẫu có đủ title/body/ảnh (41,25%)** | Đạt quy mô pilot; **chưa** xác nhận quyền nguồn, resume và độ đúng ngữ cảnh từng mẫu |
| Mục tiêu 200–500 mẫu hợp lệ; nhãn/nhóm, lý do ảnh thiếu | [PR #67, recovery-summary](https://github.com/ngnsusinn/anti-fake-news/blob/75a72e50766b6a4e5855626ea056cad161ecae61/reports/recovery-summary.md): **23.196 = 400 đã thu hồi + 675 loại + 22.121 chờ**. Trong 400 có **286 cả body+ảnh**, 99 chỉ body, 15 chỉ ảnh; 4 nhóm nguồn–nhãn ×100 | Đạt mốc số **ứng viên thu hồi**, chưa phải 400 mẫu đã qua audit và split; thiếu manifest/checksum có thể QA truy cập và số nhóm sự kiện độc lập |
| Ba cấu hình, quy tắc chọn bằng Validation | DESIGN §4 có ba cấu hình; #4 vẫn mở | Chờ giao thức được phê duyệt |
| CLIP ViT-B/32 chạy CPU, RAM, số chiều | [PR #68](https://github.com/ngnsusinn/anti-fake-news/pull/68): Windows x64/Python 3.13, CLIP **16/16 online + 16/16 offline**, embedding **512 chiều**, CPU 12 luồng logic, RAM khả dụng 29,7 GiB; trung vị **118,4 ms online / 84,8 ms offline mỗi ảnh** trên dữ liệu tổng hợp | Có bằng chứng smoke do PR báo cáo; cần BACKEND review, chốt Python và đối chiếu với **máy demo thực tế** nếu khác |
| Hợp đồng API và Extension | `api-contract.md` / `inference-interface.md` v0.1.1 là bản đề xuất; #8 cảnh báo kiểm tra lại | Chờ Backend/ML/Extension đồng ý |
| Backend scaffold | README mô tả FastAPI local; health chưa sẵn sàng, real `/predict` trả 503; mock phải bật rõ ràng | Đã có khung, **không** chứng minh suy luận thật |
| Extension smoke | [PR #65](https://github.com/ngnsusinn/anti-fake-news/pull/65) đã merge vào `main` tại `75a7b32`. QA chạy lại 2/2 test phiên, 3 nhóm Chromium smoke và ca hồi quy chữ ẩn bằng CSS | Đạt phạm vi trích DOM và phiên theo tab tuần 1 |
| Quy trình/ma trận QA | Đã soạn `docs/working-agreement.md`, `docs/test-plan.md`, `tests/fixtures/README.md` | Chờ DATA review và CODEOWNER duyệt |

## 2. Đối chiếu hợp đồng, dữ liệu và bằng chứng còn thiếu

- **Tài liệu gốc:** Đã đối chiếu [phiếu đăng ký đề tài](../output/pdf/phieu-dang-ky-de-tai-07.pdf), [DEFINE](../DEFINE.md) và [DESIGN](../DESIGN.md). Phiếu xác định thân bài tiếng Anh, tiêu đề tùy chọn và một ảnh đại diện. Dòng phạm vi ngôn ngữ trên `main` khác phiếu. Bản sửa DEFINE và cấu hình thực nghiệm nằm tại [PR #68](https://github.com/ngnsusinn/anti-fake-news/pull/68), chờ Integration/ML rà. [API v0.1.1](../docs/api-contract.md) tiếp tục chờ chốt các quyết định tích hợp. DESIGN trên `main` hiện không có §8/§12 mà một số issue dẫn chiếu. Phiếu đề tài ghi demo Streamlit; phạm vi triển khai của DESIGN và repo hiện dùng Chromium Extension với FastAPI cục bộ. Ghi nhận khác biệt này để nhóm đối chiếu khi bàn giao.
- **DATA:** Pilot 165/400 đủ cả title/body/ảnh theo điều kiện kỹ thuật. Batch báo cáo 286/400 ứng viên body+ảnh; các mẫu chưa được thẩm định đúng bài/ảnh và quyền dùng nguồn. Báo cáo batch nêu `SHA256SUMS` nhưng chưa có đường dẫn artifact bất biến mà QA xác minh được. `event_id` chưa gán đầy đủ, nên chưa chứng minh chia theo nhóm 70/15/15 không leakage.
- **ML:** PR #68 cung cấp checkpoint `openai/clip-vit-base-patch32` revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`, 512 chiều; kết quả Windows là smoke encoder bằng ảnh tổng hợp, **không** chứng minh suy luận end-to-end hoặc Macro-F1.
- **Extension:** PR #65 đã sửa lỗi lấy chữ ẩn trong `extract.js` và qua QA tại `4d0ee6d`.
- **Backend:** `main` còn đường real-mode `/predict` trả 503; mock dev/test không phải predictor thật. Hợp đồng v0.1.1 đang chờ quyết định liên vai trò.
- **Trạng thái issue:** #2, #3, #4, #6, #10, #11 và #15 vẫn mở tại thời điểm kiểm tra. #8 vẫn cần kiểm tra lại và còn checklist chốt hợp đồng chưa duyệt.

## 3. Bằng chứng kiểm tra độc lập

Trên `main` tại `75a7b32`, Windows x64/Python 3.13.0:

- Backend `python -m pytest -q` từ thư mục `backend` đạt 90/90.
- `python tests/smoke_local.py` ở chế độ mặc định: `/health` 200, `model_ready=false` và `/predict` 503.
- `python tests/smoke_local.py --mode mock`: `/health` 200, `model_ready=true` và `/predict` 200 với phản hồi tổng hợp.
- Extension đạt 2/2 test phiên, Chromium smoke và ca chữ ẩn sau khi merge #65.

## 4. Các bước xác minh còn lại

1. Dùng mốc đã merge #65 và chạy lại Backend/Extension khi nghiệm thu các thay đổi tích hợp.
2. DATA bàn giao **manifest/snapshot và SHA256SUMS có quyền QA truy cập**, bản audit nguồn/quyền và nhóm sự kiện độc lập. Các số tổng đã đối soát về mặt số học nhưng chưa xác nhận byte/chữ ký bản chốt.
3. ML/BACKEND review [PR #68](https://github.com/ngnsusinn/anti-fake-news/pull/68), thống nhất Python, xác nhận máy Windows đã đo có phải máy demo cuối cùng hay không; chạy lại smoke nếu khác cấu hình.

Số liệu pilot/batch ở bảng lấy từ báo cáo/PR có liên kết; kiểm tra số học bằng QA: **400 + 675 + 22.121 = 23.196**, **286 + 99 + 15 = 400**. Số liệu pilot 165 và batch 286 thuộc hai đợt/phạm vi khác nhau, **không** được diễn giải là tỷ lệ cải thiện mô hình.

## 5. Quyết định checkpoint

- **No Go đối với nghiệm thu hoàn tất tuần 1 hoặc demo mô hình thật**: đã có pilot 400 bản ghi (390 URL được gửi yêu cầu bài đầu tiên) và báo cáo 400 mẫu thu hồi, có CLIP CPU smoke; **nhưng** thiếu kiểm định quyền/nội dung và nhóm độc lập, hợp đồng chưa duyệt và chưa có luồng suy luận thật.
- **Conditional Go cho các việc độc lập tuần 2**: tiếp tục kiểm tra schema/fixture, test hợp đồng tổng hợp, UX Extension và validator chia tập. Không tự mở Test hoặc thay đổi contract chưa duyệt.
- **Blocker cần xử lý (đề nghị cập nhật trước checkpoint kế tiếp 30/11/2026):** DATA `locnguyen230` (#2/#3: manifest/checksum, quyền, nhóm); INTEGRATION `fulord26` (#4: protocol/ngôn ngữ); ML `0xDa1Vu` và BACKEND `Phuc1232` (#6/#8: môi trường và contract); QA `dangnguyen0512` (thu bằng chứng và review). Xem [sổ rủi ro](../docs/risk-register.md).
- **Phê duyệt bắt buộc:** reviewer DATA và CODEOWNER `@ngnsusinn`. Chỉ ký checkpoint và đánh dấu #15 Done khi có URL bằng chứng thực, quyết định, ngày giờ và những giới hạn còn lại.

Nguồn đối chiếu: [DEFINE](../DEFINE.md), [DESIGN](../DESIGN.md), [hợp đồng API](../docs/api-contract.md), [Issue #15](https://github.com/ngnsusinn/anti-fake-news/issues/15).
