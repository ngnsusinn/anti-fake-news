# Mock dev/test — hợp đồng hiện tại v0.2.0

Mock cần đồng thời AFN_ENVIRONMENT=dev hoặc test và AFN_PREDICTOR_MODE=mock.
Từ backend, dùng môi trường hiện hữu:

```powershell
$env:AFN_ENVIRONMENT="dev"
$env:AFN_PREDICTOR_MODE="mock"
# Cung cấp AFN_DEMO_TOKEN riêng trong .env hoặc process environment.
..\.venv\issue9\Scripts\python.exe -m app
```

Từ #22/#23, mock dùng cùng validation với real: X-Demo-Token bắt buộc, form/ảnh JPEG/PNG
hợp lệ và các trần byte/pixel. Secret chưa cấu hình trả 401. Xem ví dụ và lỗi trong
[API contract](api-contract.md), fixture `backend/tests/fixtures/api/v0.2.0/`.

Mock vẫn trả cố định label=real, fake_score=0.42, model_id=dev-mock-not-a-model,
model_version=mock-v0.1.1, text_truncated=false. ID/model version mock không đổi vì provider
không đổi; HTTP contract là v0.2.0. Không dùng kết quả này làm bằng chứng dự đoán hay accuracy.
Transport decode/kiểm tra ảnh, nhưng mock Predictor bỏ qua nội dung. Thời gian đo quanh Predictor.

Real không fallback mock. Sau validation, real chưa có model trả 503 và echo UUID hợp lệ.
Health phản ánh adapter not_loaded/ready/error; provider lỗi chuyển error, restart mới phục hồi.
CORS, model loader và warm-up vẫn thuộc #37/#38. Không sửa Extension.

Smoke tạo token ngẫu nhiên và PNG tổng hợp, kiểm tra health/auth/predict, rồi dừng server của nó:

```powershell
..\.venv\issue9\Scripts\python.exe tests/smoke_local.py
..\.venv\issue9\Scripts\python.exe tests/smoke_local.py --mode mock
```

Chạy tuần tự. Bằng chứng hiện tại ở [báo cáo #22/#23](implementation-issues-22-23.md).

# Lịch sử AFN-009 (2026-11-19)

Phần dưới được giữ nguyên làm hồ sơ lần triển khai #9. Các mô tả no-auth/no-decode,
503 không đọc body, fixture v0.1.1 và deferred #22/#23 bên dưới **không còn là hành vi hiện tại**.
Các kết quả test và trạng thái GitHub bên dưới chỉ thuộc lần chạy lịch sử đó.

## Yêu cầu, phân định trách nhiệm và trạng thái review (2026-11-19)

| Yêu cầu / Nguồn | Triển khai | Kiểm chứng (Verification) | Phụ trách / Trạng thái |
| --- | --- | --- | --- |
| #9: Predictor + not_loaded/ready/error | `inference_adapter.py`, Predictor protocol hiện có | Kiểm thử trạng thái/lỗi của Adapter | Backend đã triển khai; ML đang chờ review |
| #9: mock dev/test cố định | `dev/mock_predictor.py`, `dev/transport.py`, `main.py` | Kiểm thử mock HTTP, lỗi đầu vào, correlation, fixture | Backend; Extension đang chờ consumer review |
| #9: opt-in rõ ràng, không fallback thực tế | Settings/environment + factory vòng đời | Cấu hình, lỗi factory và kiểm thử hồi quy chế độ real | Backend đã triển khai |
| #9: health an toàn / real 503 khi chưa sẵn sàng | Health adapter DI + bộ xử lý lỗi | Kiểm thử quyền riêng tư, thiếu artifact, không đọc body và smoke test | Backend đã triển khai |
| #9: fixtures/docs có phiên bản; không sửa loader | `backend/tests/fixtures/api/v0.1.1`, tài liệu này | Xác thực fixture và rà soát diff có giới hạn | Backend sẵn sàng bàn giao cục bộ |
| Tiền đề đã hoàn thành: #7 + #8 / ML review | Nền tảng hiện có và hợp đồng đề xuất | Đã đọc các issue/comment hiện có; chưa có phê duyệt mới | MỘT PHẦN (PARTIAL): môi trường và review hợp đồng liên vai trò vẫn đang chờ |

Issue #9 trên GitHub hiện đang open và chưa có bình luận khi kiểm tra. Live #7/#8 được đánh dấu
`closed` với `state_reason=not_planned`, trong khi nội dung của chúng ghi cần mở tiếp
để chờ kiểm tra lại/review và hợp đồng v0.1.0 chỉ là bản thảo. Các bình luận của chúng chỉ ghi
"check my pull request". Không diễn giải trạng thái closed như là sự phê duyệt liên vai trò.
Nhánh cục bộ là `dev-be`, baseline `d134971`; ban đầu chỉ có `.agents/` là untracked.
Thư mục skill đó được giữ nguyên. `DIAGRAMS.md` không tồn tại; `DESIGN.md` vẫn chỉ có
các phần 1–4 mặc dù issue có tham chiếu đến §8.1–8.4. Các quyết định hiện có về ngôn ngữ,
bytes/RGB, timeout, tổng dung lượng và chính sách xác thực vẫn chưa được giải quyết.

ML review ngữ nghĩa/môi trường của Predictor; Extension review việc tiếp nhận health/kết quả
và dấu hiệu nhận biết mock; repo owner review toàn bộ tệp theo CODEOWNERS. **Chưa có phê duyệt nào
từ ML/Extension được xác nhận và không có yêu cầu review bên ngoài nào được gửi trong lần chạy này.**
Tài liệu này ghi nhận sự thay đổi hợp đồng để bàn giao; đây không phải biên bản phê duyệt. Không có thao tác
commit, push, PR hay biến đổi trạng thái issue nào được ủy quyền hoặc thực hiện cho #9.

## Bằng chứng thực thi (Execution evidence)

Môi trường kiểm thử hiện tại: Windows x64, Python **3.13.1** từ lệnh `python` có sẵn.
File `..\.venv\Scripts\python.exe` cũ không thể khởi động vì tệp thực thi Python 3.10 của nó
không còn tồn tại. Đã tạo `.venv/issue9` mà không xóa hay ghi đè môi trường cũ; nó vẫn được Git bỏ qua (ignored).

Trong bản checkout này, từ thư mục `backend`, hãy dùng
`..\.venv\issue9\Scripts\python.exe -m app` với các cờ nêu trên để chạy môi trường
đã cài đặt. Sử dụng chính trình thông dịch này cho pytest, pip check và các script smoke;
file `..\.venv\Scripts\python.exe` ban đầu vẫn không thể sử dụng.

Đã cài đặt các gói yêu cầu đã ghim sẵn có vào môi trường mới. Lần thử đầu tiên trong sandbox
thất bại với WinError 10013; lần thử lại sau khi cấp quyền đã thành công.
Tải `python-multipart` bằng lệnh `pip download --python-version 3.10
--only-binary=:all: --no-deps --dest .venv/issue9/wheels python-multipart` và cài đặt
wheel **0.0.32** đã phân giải với tùy chọn `--no-index`, sau đó thêm bản ghim chính xác đó.
Tất cả các bản ghim khác được giữ nguyên. Ràng buộc giải quyết này duy trì yêu cầu baseline cũ;
đây không phải là việc chạy lại trên Python 3.10 hay bằng chứng về tính tương thích với ML.

Lần chạy test ban đầu báo cáo 88 passed và 2 lỗi setup do ID tham số tự sinh quá dài;
sau khi gán các ID ngắn, kết quả thực tế của toàn bộ bộ test là **89 passed in 1.73s**.
Kết quả xác minh cuối cùng được ghi lại bên dưới.

Tất cả các lệnh dưới đây được chạy từ thư mục `backend` sử dụng `..\.venv\issue9\Scripts\python.exe`
trừ khi có ghi chú khác. Không có công cụ lint/type-check nào được cấu hình trong repo.

| Lệnh / Kiểm chứng | Kết quả thực tế cuối cùng |
| --- | --- |
| `python -m pytest -q` sau khi bổ sung bài test hồi quy lỗi khởi động | **90 passed in 2.52s**, exit 0 |
| `python -m pip check` | **No broken requirements found.**, exit 0 |
| `python tests/smoke_local.py` | Health 200, mode real, ready false; predict 503/null UUID; child process đã dừng; exit 0 |
| `python tests/smoke_local.py --mode mock` | Health 200, mode mock, ready true; predict 200/dev-mock ID/echoed UUID; child process đã dừng; exit 0 |
| `git diff --check` / `git -c core.safecrlf=false diff --check` từ thư mục gốc repo | Không có lỗi khoảng trắng; các lệnh Git thông thường chỉ phát cảnh báo chuyển đổi LF sang CRLF |
| Kiểm tra khoảng trắng Python + `ast.parse` trên các file mới/đổi, trừ `.agents/` có sẵn | **12 tệp sửa đổi + 17 tệp mới đều đạt chuẩn** |
| So sánh `importlib.metadata.version` với từng bản ghim trong requirements | Tất cả các phiên bản đã cài đặt khớp với 28 bản ghim |
| `git diff --cached --name-only` và diff có phạm vi các file gốc | Không có file staged; design/planning/CODEOWNERS/báo cáo lịch sử không đổi |
| Python 3.10, Linux/macOS, mô hình huấn luyện thực tế, tích hợp CORS trình duyệt | **CHƯA CHẠY**; nằm ngoài môi trường/phạm vi cục bộ này |

Các thay đổi mã nguồn gồm:

- Sửa đổi: `.env.example`, `README.md`, `backend/app/config.py`,
  `backend/app/main.py`, `backend/app/predictor.py` (chỉ docstring),
  `backend/app/schemas.py` (chỉ phiên bản hợp đồng), `backend/requirements.txt`,
  `backend/tests/smoke_local.py`, `backend/tests/test_app.py`,
  `backend/tests/test_config.py`, `docs/api-contract.md`, `docs/inference-interface.md`.
- Thêm mới: `backend/app/inference_adapter.py`, `backend/app/dev/__init__.py`,
  `backend/app/dev/mock_predictor.py`, `backend/app/dev/transport.py`,
  `backend/tests/test_inference_adapter.py`, `backend/tests/test_dev_mock.py`,
  tài liệu này, và mười tệp fixture/manifest/README trong thư mục
  `backend/tests/fixtures/api/v0.1.1/`.

| Tiêu chí nghiệm thu Live Issue #9 | Trạng thái | Bằng chứng |
| --- | --- | --- |
| Mock chỉ khi có cờ dev/test tường minh; không fallback khi mô hình thật lỗi | **ĐẠT (PASS)** cục bộ | Cấu hình opt-in, factory thực, các bài test lỗi khởi tạo/gọi hàm |
| Health an toàn; chế độ real không có artifact không bao giờ ready | **ĐẠT (PASS)** cục bộ | Kiểm thử DI health/quyền riêng tư và smoke test HTTP thực tế |
| Chế độ real chưa sẵn sàng trả về 503 | **ĐẠT (PASS)** cục bộ | Kiểm thử hồi quy không đọc body/override hiện có và HTTP smoke |
| Bàn giao chỉ dành cho dev/test, fixtures có phiên bản, không sửa model_loader.py | **ĐẠT (PASS)** cục bộ | So sánh schema/HTTP của fixture có phiên bản và rà soát diff có phạm vi |
| Các điều kiện tiên quyết được chấp nhận và review ML bắt buộc | **MỘT PHẦN (PARTIAL)** | Các quyết định review của #7/#8 vẫn chưa được giải quyết; chưa có phê duyệt mới từ ML/Extension |

Triển khai đã hoàn thiện về mặt mã nguồn cho phạm vi cục bộ này. Trạng thái Done trên GitHub vẫn là
**MỘT PHẦN (PARTIAL)**, không phải là sự phê duyệt được suy đoán. Không có thao tác commit/push/PR hay biến đổi
trên GitHub nào được thực hiện. Các rủi ro còn lại là việc tích hợp mô hình thực/CORS/vận chuyển chưa hoàn thành
như đã ghi trong tài liệu và việc chờ review hợp đồng dùng chung, chứ không phải do cơ chế fallback ẩn của mock.
