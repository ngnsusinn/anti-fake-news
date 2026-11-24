# Bàn giao AFN-022 / AFN-023 — 2026-11-23

Đã triển khai và kiểm chứng local theo skill `.agents/afn-issue-implementer/SKILL.md`.
Đây là bằng chứng kỹ thuật, **không phải ML/Extension approval hay trạng thái Done**.
Chỉ làm #22/#23; không commit, stage, push, tạo PR, gửi comment/review hay đóng issue.

## Điểm xuất phát và nguồn yêu cầu

Working tree ban đầu sạch, branch `dev-be`, HEAD `2eda975` (change name commit->done issue 9).
Đã kiểm tra mã/test hiện có và các tài liệu README, DEFINE, DESIGN, planning/hợp đồng liên quan.
Không có AGENTS.md; DIAGRAMS.md không có trong checkout. DESIGN chỉ có §1–4,
trong khi issue trỏ §5/§8.4; không tự bổ sung các đặc tả còn thiếu.
Ngôn ngữ đầu vào và protocol ML còn cần xác nhận; giữ nguyên tài liệu nền.

Live [#22](https://github.com/ngnsusinn/anti-fake-news/issues/22) và
[#23](https://github.com/ngnsusinn/anti-fake-news/issues/23) đều open, 0 comments,
assignee Phuc1232; reviewer theo vai trò là ML. Đã kiểm tra lại lúc bàn giao.
Code/tests đặt trong `backend/tests/` theo layout hiện hữu, không sửa tests QA #28.
User đã xác nhận triển khai sau bước trình kế hoạch của skill.

## Thay đổi thực tế trên tệp

| Tệp | Thay đổi |
| --- | --- |
| `backend/app/validation.py` (mới) | Auth trước đọc body, streaming byte cap, bounded multipart, validation form và cleanup |
| `backend/app/image_validation.py` (mới) | MIME/format/bytes/pixel/decode/bomb; gọi EXIF/RGB helper chung và đóng RGB |
| `backend/app/errors.py` (mới) | Lỗi 400/401/413 chung, thông điệp đã làm sạch |
| `backend/app/preprocessing.py` (mới trong checkout) | Khôi phục nguyên bản module upstream ML, không sửa thuật toán |
| `backend/app/main.py` | Nối middleware/validation DI ở cả real/mock, error handler và OpenAPI |
| `backend/app/schemas.py` | Phiên bản hợp đồng/health 0.2.0; giữ tập trường và kiểu |
| `backend/app/config.py` | Chỉ sửa docstring/comment về enforcement đã có |
| `backend/app/dev/transport.py` (xóa) | Thay cầu nối mock riêng bằng validation chung, loại bỏ đường bỏ qua auth/decode |
| `backend/requirements.txt` | Thêm pillow==13.0.0 và numpy==2.5.5; 30 pins; cập nhật ghi chú môi trường |
| `backend/tests/test_request_limits.py`, `test_image_validation.py` (mới) | Auth, HTTP/ASGI streaming, boundary, ảnh, parity helper, cleanup |
| `backend/tests/conftest.py`, `test_app.py`, `test_dev_mock.py` | PNG/token tổng hợp, hành vi v0.2.0, regression DI/health/mock |
| `backend/tests/smoke_local.py` | Token ngẫu nhiên + PNG tổng hợp, auth/real/mock qua socket thật |
| `backend/tests/fixtures/api/v0.2.0/` (mới, 11 tệp) | Health/predict/error JSON, thêm 401, manifest, README |
| `.env.example`, `README.md` | Auth bắt buộc, giới hạn, môi trường hiện hữu và lệnh chạy |
| `docs/api-contract.md`, `docs/inference-interface.md` | Hợp đồng v0.2.0 và provenance/helper seam |
| `docs/dev-mock.md` | Hướng dẫn hiện tại; giữ nguyên phần báo cáo lịch sử #9 và đánh dấu rõ |
| Tài liệu này (mới) | Ma trận nghiệm thu, lệnh/kết quả và review còn thiếu |

Không đổi Predictor protocol, inference_adapter, mock provider, model loader, ML training,
Extension, tests QA, DEFINE/DESIGN/planning, báo cáo #7/#8 hoặc fixtures v0.1.1.
Không có model/checkpoint, .env thật, bài báo/ảnh người dùng, secret hay cache mới trong diff.

Module preprocessing lấy từ PR #68, commit `9b5a0ab1b0ce19cf04467e845a8772713f858da8`.
`git hash-object backend/app/preprocessing.py` trả blob
`c235ab427f0ecb8f3d6f9c2a0b0908c5712f718d`, khớp upstream.
Pillow/NumPy pin khớp `ml/requirements.txt` tại commit đó.
Các hàm text/embedding kèm module nguyên bản không được gọi bởi transport.

## Ma trận yêu cầu và nghiệm thu

| Yêu cầu / nguồn | Code / bằng chứng | Trạng thái / owner |
| --- | --- | --- |
| #22 token trước xử lý tốn tài nguyên | ASGI receive sentinel không được gọi khi thiếu token; thiếu/sai/trùng/unconfigured 401 | PASS local / Backend |
| #22 UUID/title/text/image; 400 thay 422 | Kiểm thử missing parts, UUID sai/trùng, blank text, 50.001 text, 501 title; OpenAPI không 422 | PASS local / Backend |
| #22 total bytes kể cả không có/khai nhỏ Content-Length | ASGI nhiều chunk, exact 12 MiB và +1, header oversized không đọc body | PASS local / Backend |
| #22 ảnh 10 MiB còn overhead | Ảnh PNG hợp lệ được pad đúng 10 MiB + 50.000 emoji + title 500 thành công trong mock | PASS local / Backend |
| #23 MIME/bytes/decode/bomb | Unit và HTTP real/mock trả lỗi đã làm sạch, không gọi provider với ảnh sai | PASS local / Backend |
| #23 boundary byte/pixel | 10 MiB nhận/+1 từ chối; đúng 20.000.000 pixel nhận, vượt trần từ chối | PASS local / Backend |
| #23 helper EXIF/RGB chung | Hash upstream khớp; JPEG EXIF và RGBA/LA/P/L/RGB/16-bit parity | PASS local / Backend; ML review pending |
| #23 đóng tài nguyên | RGB closed; spool success/error/truncated/disconnect/image cap/total cap đều closed | PASS local / Backend |
| Hợp đồng/version/fixtures | API/DI docs v0.2.0, schema/manifest/HTTP assertions | PASS local; consumer review PARTIAL |
| Nghiệm thu phụ thuộc #7/#8 và #5/#22, reviewer ML | Không có phê duyệt mới; upstream handoff/protocol còn pending | BLOCKED cho Done / ML + Backend |
| Real model accuracy/performance; Extension CORS | Không triển khai #37/#38/#39/#52 hay sửa Extension | NOT RUN, ngoài phạm vi |

PASS ở đây là kiểm chứng kỹ thuật cục bộ; mock không chứng minh chất lượng mô hình.
Auth policy hiện dùng 401 cho mọi lỗi token; chưa có policy 403. Giá trị body cap mặc định
12 MiB đã thực thi nhưng còn chờ consumer review. Predictor vẫn nhận bytes ảnh gốc;
RGB validation được đóng, provider thật sẽ gọi cùng helper để decode lại.

## Lệnh đã chạy và kết quả

Môi trường: Windows x64, Python 3.13.1, tái sử dụng `.venv/issue9`; không tạo venv mới.
`.venv` và `.venv/verify` cũ trỏ Python 3.10 không còn tồn tại, giữ nguyên.
Pip ban đầu bị sandbox chặn mạng (WinError 10013), đã chạy lại với quyền được cấp.
Có cài thử Pillow 11.3.0/NumPy 2.2.6 trước khi đối chiếu manifest; sau đó thay bằng
Pillow 13.0.0/NumPy 2.5.5. Hai bản cuối mới là pins thực tế; không giữ fallback phiên bản cũ.

Các lệnh Python dưới đây chạy từ `backend`, dùng đầy đủ interpreter
`..\.venv\issue9\Scripts\python.exe` (viết ngắn thành `python` trong bảng).

| Lệnh / kiểm chứng | Kết quả thực tế |
| --- | --- |
| `python -m pytest -q --tb=short` trong lúc phát triển | 115 passed, 3 failed; hai test dùng body không phải multipart nên nhận 400 trước cap; một lỗi cleanup truncated file. Pytest còn báo ResourceWarning vì leak đó |
| Cùng lệnh sau sửa cleanup/test stream | 118 passed in 2.13s, exit 0 |
| Cùng lệnh sau bổ sung regression/header/bytes seam | **129 passed in 4.30s**, exit 0; warnings được cấu hình thành errors |
| `python -m pip check` | **No broken requirements found.**, exit 0 |
| `python tests/smoke_local.py` | Health 200 real/false; thiếu token 401; valid request 503 echo UUID; stopped server True, exit 0 |
| `python tests/smoke_local.py --mode mock` | Health 200 mock/true; thiếu token 401; valid request 200 dev-mock-not-a-model; stopped server True, exit 0 |
| Script `importlib.metadata.version` so từng dòng requirements | **Installed versions match all 30 pins**, exit 0 |
| Script `ast.parse` mọi backend Python source | **All backend Python sources parse**, exit 0 |
| `git hash-object backend/app/preprocessing.py` tại repo root | Blob khớp upstream nêu trên |
| `git -c core.safecrlf=false diff --check` tại root | Exit 0, không lỗi whitespace |
| `git diff --cached --name-only` | Rỗng, không stage |
| `git status --short`, `git diff --stat`, scoped source diff | Chỉ tệp nêu trong bảng; không commit/push/GitHub mutation |
| Lint/type checker riêng | NOT RUN: repo không cấu hình công cụ |
| Python 3.10, Linux/macOS, full ML runtime, model evaluation, browser CORS | NOT RUN |

Git thông thường có cảnh báo LF→CRLF, không phải lỗi test. Một lần cập nhật docs bằng apply_patch
bị từ chối vì hai operation nhắm cùng path; chưa ghi tệp ở lần đó, đã ghi lại thành công sau đó.
Các lỗi kiểm thử trong quá trình phát triển ở trên đã sửa; không báo chúng là thành công ban đầu.

## Blocker, review và giới hạn còn lại

- ML review bắt buộc cho #22/#23 chưa có. #5 có báo cáo merge PR #68 nhưng handoff/protocol #4
  còn pending; #7/#8 có trạng thái closed/not_planned mâu thuẫn với ghi chú review chưa xong.
  Không suy diễn các trạng thái đó thành approval. Cần ML/Backend xác nhận version helper,
  bytes/RGB seam, môi trường và các quyết định protocol để đánh dấu Done.
- Extension cần xác nhận token ở mọi mode, thứ tự lỗi mới, correlation/null UUID,
  fixture v0.2.0 và giá trị cap. Chưa gửi thông báo/comment hay yêu cầu review bên ngoài;
  tài liệu này chỉ chuẩn bị bàn giao. CODEOWNERS/repo owner vẫn phải review thay đổi.
- Không có blocker ngăn chạy Backend local trên môi trường đã kiểm tra. Không có mô hình thật;
  real 503 là hành vi có chủ đích. Không chứng minh accuracy, độ trễ ML hoặc tích hợp browser.
- Parser cleanup dùng API nội bộ của Starlette **1.7.0 đã pin**, có regression cho các đường lỗi.
  Khi nâng Starlette phải chạy lại các test này. Full runtime ML upstream khác môi trường Windows
  đã kiểm tra; chưa tuyên bố tương thích toàn bộ training/inference.
- Không sửa hay tự triển khai #28/#37/#38/#39/#52 và không đổi secret/config thật của người dùng.

Kết quả local sẵn sàng để review; hai issue vẫn open. Không có commit/PR URL để báo cáo.
