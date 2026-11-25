# AFN-035: ba gói ứng viên thật (dataset ml-v2)

Ngày xuất: 25/11/2026, macOS M1, CPU, CLIP ViT-B/32 đã ghim. Dựa trên kết quả #34
([ml-train-validation.md](ml-train-validation.md)): fit trên Train (153 mẫu), chọn trên Validation (32 mẫu).
**Test không được nạp**, gói không lưu dự đoán nào.

## Gói đã xuất

`ml.export_artifacts` → `backend/artifacts/candidates-v2/` (gitignored, không commit).
Định dạng `afn-model-bundle-v1` (JSON + `.npy`, không pickle), `is_fixture: false`, `status: candidate`
(chuyển sang trạng thái khác chỉ khi #49 freeze).

| Gói | model_version | Số chiều | C | Ngưỡng | Macro-F1 Val | Round-trip max\|Δ\| | Nhãn khớp |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| text-only | `text-only-20261125-275718e3163b` | 5000 | 10 | 0,60 | 0,686 | 0 | có |
| image-only | `image-only-20261125-cd863cbaabf5` | 512 | 10 | 0,30 | 0,536 | 5e-16 | có |
| multimodal | `multimodal-20261125-105d5f14e79a` | 5512 | 100 | 0,70 | 0,624 | 0 | có |

Round-trip: bộ xuất nạp lại từng gói bằng `app.model_bundle.load_bundle` và so điểm/nhãn với scikit-learn
trên Validation (atol 1e-9). C và ngưỡng trùng với lần chạy #34 (`cache/runs/20261125T144056Z`).

## Bàn giao Backend (#24/#37)

- Gói nào được dùng cho demo sẽ quyết định ở #49. Theo thiết kế, `POST /predict` dùng Multimodal.
- Backend nạp bằng `app.model_bundle.load_bundle(<dir>)` (xem [docs/model-bundle.md](../docs/model-bundle.md)).
- Gói không nằm trong git. Để tạo lại trên máy khác:

```sh
# cần data/private/ml-v2 từ #34 (ml.prepare_dataset)
H=data/private/ml-v2/train-validation
.venv/bin/python -m ml.export_artifacts --manifest $H/manifest.jsonl --split $H/split.csv --image-root data \
    --out backend/artifacts/candidates-v2 --offline
```

Quá trình fit là tất định (liblinear, seed 42, CLIP eval), nên lần xuất lại phải cho cùng C/ngưỡng và cùng điểm Validation.
`model_version` có chứa ngày xuất.

## Còn mở

- Phụ thuộc #34 (PR riêng) và việc DATA/QA xác nhận dataset ml-v2.
- #24 (Integration) cần xác nhận schema gói trên dữ liệu thật.
