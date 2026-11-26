# AFN-058 · Audit freeze và kết quả Test

**26/11/2026 · BLOCKED với Test thật.** QA `dangnguyen0512`, reviewer ML
`0xDa1Vu`. Snapshot [`aefb0ef`](https://github.com/ngnsusinn/anti-fake-news/commit/aefb0efc2b18fbb3a06d1766d1471ec188933eaf).

| Hạng mục | Kết quả |
| --- | --- |
| Hash public trên snapshot | **15/15 khớp:** 13 hash tệp mã/cấu hình, hash tệp lựa chọn và canonical hash của hồ sơ trong chữ ký ML. Tính trên byte UTF-8 của đúng revision. |
| Bản freeze | [Hồ sơ](../release/model-freeze.json) `draft`. ML đã ký canonical hash `7afd69ded04c225beb6537295555178d901383983a19b552d6e27c10aac983f8`. SHA của bundle và manifest/split Train/Val cục bộ chờ QA kiểm trực tiếp. [Biên bản #49](pre-test-signoff.md). |
| Dữ liệu / nguy cơ rò rỉ | Split `ml-v2`, run `20261126T024649Z`. Audit [#29](leakage-audit.md) ghi 21 hostname publisher có mặt ở nhiều split và thiếu event ID. Ghi giới hạn này trong diễn giải Test. |
| Test cuối | Chưa có `test-metrics.json` hoặc predictions #50 được bàn giao. Chưa có kết quả, số đếm hoặc ma trận Test có thể nghiệm thu. |
| Công cụ audit | [`audit_test_predictions.py`](../scripts/audit_test_predictions.py) đối chiếu chữ ký, thứ tự thời gian, hash tập tin, log rerun, split và cùng ID/nhóm. Tái tính macro-F1, accuracy, metric từng lớp, ma trận và Δ của ba cấu hình từ nhãn lưu và kiểm từng điểm theo ngưỡng đã ký. |

Đã chạy `python -m unittest discover -s tests -p test_audit_test_predictions.py -v`:
**7/7** trên fixture tổng hợp, gồm Δ âm, ngưỡng bằng điểm, sai hash hoặc ID
trùng, nhãn sai, metrics lệch, thời điểm trước ký và rerun thiếu lý do.
Công cụ chỉ mở hồ sơ và các tệp bàn giao CSV/JSON/JSONL, không nạp model.

## Chạy audit sau bàn giao #50

ML bàn giao metrics, predictions, CSV split QA và CSV split Train/Val đã
ẩn Test ID qua kho riêng. QA đối chiếu bundle, mã, config và hash
manifest/split với hồ sơ đã ký bằng `python -m ml.freeze verify --bundle-root backend/artifacts`
cùng các đường dẫn bàn giao nếu khác mặc định. Đối chiếu hash manifest Test
và hash code/bundle của đợt chạy đã lưu trước khi nhập báo cáo cuối.
Từ repo chạy:

```powershell
python scripts/audit_test_predictions.py --freeze release/model-freeze.json --metrics reports/test-metrics.json --predictions reports/test-predictions.jsonl --locked-split data/private/ml-v2/train-validation/split.csv --qa-split data/private/ml-v2/qa-only/split.csv
```

Giữ predictions và split chứa ID trong vùng bàn giao riêng. Lưu kết quả
tổng hợp, hash, giờ chạy, reviewer và lý do kỹ thuật của mọi lượt rerun.
Sai hash, version, mapping hoặc metrics thì ghi BLOCKED và báo ML. Công việc này không chạy lại suy luận hoặc điều chỉnh tham số bằng Test trong công việc này.
