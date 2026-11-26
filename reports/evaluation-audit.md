# AFN-058 · Audit freeze và kết quả Test

**26/11/2026 · PASS kỹ thuật trên 33 mẫu, chờ ML review.** QA
`dangnguyen0512`, reviewer `0xDa1Vu`. Freeze ký đủ trên
[`main 4175c97`](https://github.com/ngnsusinn/anti-fake-news/commit/4175c974e69d9364aff4428aade3acb7e39f4824).
Đầu vào kết quả ML lấy từ [PR #123](https://github.com/ngnsusinn/anti-fake-news/pull/123)
tại [`657bfe7`](https://github.com/ngnsusinn/anti-fake-news/commit/657bfe7360ee434eab64cd655c8d6e5a9dec6c71).

| Hạng mục | Kết quả |
| --- | --- |
| Freeze và phiên bản | `ml.freeze verify` trả 0 với hai chữ ký và cả ba bundle. SHA-256 byte của hồ sơ cũng trùng `inputs.freeze_sha256` trong #50. C, ngưỡng, model ID/version, 13 hash tệp mã/cấu hình, tệp lựa chọn, manifest Train/Val và split ẩn Test ID khớp đúng hồ sơ. |
| Thời gian và log chạy | Test lúc 14:24:20 UTC+7 ngày 26/11, sau hai chữ ký. Marker và JSON cùng thời điểm. Một lượt `first run`, `refit: false`. |
| Predictions và chia tập | 33 ID duy nhất, 33 nhóm, 17 fake và 16 real. Train/Val giữ nguyên. Dùng 33 nhóm duy nhất làm khóa để điền lại ID Test vào bản CSV ẩn từ predictions đã khớp hash. CSV tái tạo trùng SHA-256 được #50 ghi cho CSV QA đầy đủ. Công cụ đối chiếu coverage, ID/nhóm, mapping, nhãn theo ngưỡng và phiên bản ở từng dự đoán. |
| Metrics | Tái tính accuracy, Macro-F1, precision/recall/F1/support và ma trận cả ba cấu hình. Khớp metrics và ba CSV tổng hợp của #50. Δ Macro-F1 Multimodal − Text-only = **−0,0935**. |
| Giới hạn | 21 hostname publisher vắt qua các split và thiếu event ID. Audit đối chiếu nhãn đã lưu và split. Hash manifest Test được ghi trong #50, còn việc đối chiếu byte của chính manifest Test cần bản bàn giao riêng nếu reviewer yêu cầu. [Audit dữ liệu #29](leakage-audit.md) |

| Tệp dùng trong audit | SHA-256 |
| --- | --- |
| Freeze hai chữ ký | `cc583fc991612874c1b465939aa74485fd3fe6fb8527b0df731b493239951518` |
| Predictions #50 | `75ad8eae9f9bc346be2deca5ea8c3628edc1327058c4ccf88e137f94640bfe82` |
| CSV đã ẩn ID Test | `81058045c8397ed9cce8645267466e79a2fc346606865e05ade9b303b77b9c1f` |
| CSV QA đầy đủ, khôi phục theo nhóm | `5594cda3a17d37b1d39d93315125030d0229d7ef03ffb6551efa5fba2ee1be73` |

## Tái kiểm

```powershell
python -B scripts/audit_test_predictions.py --freeze release/model-freeze.json --metrics reports/test-metrics.json --predictions <predictions> --locked-split <id-withheld-csv> --qa-split <qa-csv>
```

Lệnh trả `PASS` trên dữ liệu Test đã lưu. Suite
`python -B -m unittest discover -s tests -p test_audit_test_predictions.py -q`
đạt 7/7 trên fixture tổng hợp, gồm hash sai, ID trùng, nhãn sai ngưỡng,
metrics lệch, chạy trước ký và rerun thiếu lý do. Công cụ chỉ đọc dữ liệu
đã lưu. Giữ CSV chứa ID và predictions ở kho riêng. ML review bằng chứng
trước khi chuyển #58 sang Done. [Biên bản #49](pre-test-signoff.md)
