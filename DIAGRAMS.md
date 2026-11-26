# Sơ đồ đối chiếu bản tích hợp

Mã nguồn ngày 26/11/2026. [Thiết kế](DESIGN.md) · [Ma trận nghiệm thu](reports/final-report.md)

## Suy luận từ Extension

```mermaid
flowchart LR
    Tab["Tab đang xem"] --> Popup["Popup trích bài và chọn ảnh hợp lệ đầu tiên"]
    Popup -->|"Phân tích: multipart và UUID"| API["FastAPI v0.2.0 trên loopback"]
    API -->|"Xác thực và kiểm đầu vào"| Model["Multimodal TF-IDF + CLIP"]
    Model --> API
    API -->|"Nhãn, điểm và phiên bản"| Popup
```

Gói unpacked dùng popup. Luồng sửa nội dung và chọn/tải ảnh thủ công đang
chờ xác nhận theo [#43](reports/e2e-real-model.md).

## Train, freeze và Test

```mermaid
flowchart LR
    Train["Train: fit"] --> Validation["Validation: chọn C/ngưỡng"]
    Validation --> Freeze["#49: hash và hai chữ ký"]
    Freeze -->|"Sau khi verify"| Test["#50: chấm Test và lưu predictions"]
    Test --> Audit["#58: tái tính metrics từ predictions"]
    Audit --> Report["#59 và #60: báo cáo và nghiệm thu"]
```

Hồ sơ đã có cả hai chữ ký. QA tái tính từ predictions và khớp metrics của ML.
[Bằng chứng #58](reports/evaluation-audit.md) · [Biên bản trước Test](reports/pre-test-signoff.md)
