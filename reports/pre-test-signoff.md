# Biên bản trước khi mở Test · AFN-049

**26/11/2026 · BẢN NHÁP, CHƯA KÝ. Test vẫn khóa.** Biên bản này kèm hồ sơ
[`release/model-freeze.json`](../release/model-freeze.json) (schema `afn-model-freeze-v1`).
#50 chỉ chạy khi hồ sơ có chữ ký của cả ML và QA, và `ml.freeze verify` khớp với file
trên đĩa. Bản nháp không cho phép chạy Test.

## Hồ sơ freeze ghi gì

| Mục | Giá trị trong bản nháp hiện tại |
| --- | --- |
| Dữ liệu | Manifest Train/Val `a42af272…`, split ẩn ID Test `81058045…`, 153 Train / 32 Val / 33 Test khóa |
| Protocol | `configs/experiment.yaml` `11dab478…`, trạng thái `proposed` |
| Lựa chọn | `configs/selected-models.json`, run `20261125T145232Z`, chọn trên Validation |
| Text-only | `text-only-20261125-275718e3163b`, C = 10, ngưỡng 0,60 |
| Image-only | `image-only-20261125-cd863cbaabf5`, C = 10, ngưỡng 0,30 |
| Multimodal | `multimodal-20261125-105d5f14e79a`, C = 100, ngưỡng 0,70 |
| Artifact | SHA-256 của `metadata.json` và từng mảng `.npy`/vocabulary của ba bundle |
| Mã | SHA-256 của các file quyết định đặc trưng, điểm và lệnh Test, kèm commit git |
| Nhãn | `{"0": "real", "1": "fake"}`, lớp dương `fake`, so sánh `>=` ngưỡng |

`collect` từ chối nếu hash trong bundle, trong `selected-models.json` và trên đĩa không
khớp nhau. Lệnh chỉ đọc gói Train/Validation. Chữ ký ký lên hash chuẩn của toàn bộ hồ
sơ: sửa bất kỳ trường nào sau khi ký sẽ làm cả hai chữ ký mất hiệu lực.

## Blocker do script tự phát hiện

| Blocker | Owner | Cách gỡ |
| --- | --- | --- |
| Protocol còn `proposed` | Integration `fulord26` (#4) | Đổi `status: locked` qua PR. Hash config sẽ đổi, nên ML chạy lại Train/Val và export (xem bên dưới). |
| Mã chưa commit | ML `0xDa1Vu` | Tự hết khi PR này và PR #50 merge. |
| Chưa có lệnh Test cuối (`ml/evaluate_test.py`) | ML `0xDa1Vu` (#50) | Lệnh phải merge trước khi freeze để mã đánh giá nằm trong snapshot. |

## Điều kiện cần người xác nhận

QA ký nghĩa là đã kiểm từng dòng dưới đây trên cùng hồ sơ.

- [ ] **Split được chấp nhận.** [Audit #29](leakage-audit.md) đang `BLOCKED`: 21 hostname
      publisher đề xuất xuất hiện ở nhiều split và còn 2 cặp sự kiện ứng viên qua split.
      DATA `locnguyen230` (#31) và QA `dangnguyen0512` chốt một trong hai hướng:
      giữ `ml-v2` và ghi rõ giới hạn, hoặc dùng bản nối hostname (116/26/33, giữ nguyên
      33 ID Test). Nếu đổi split thì ML chạy lại toàn bộ Train/Val, export và parity.
- [ ] **Chưa dùng Test để chọn cấu hình.** `selected-models.json` ghi `test_split.loaded: false`.
      Audit #29 đã xếp lại độc lập 75 điểm lưới và khớp C/ngưỡng.
- [ ] **Parity.** [Báo cáo parity](inference-parity.md) mục 3b: ba cấu hình PASS trên 32 mẫu
      Validation, max |Δ| = 0. Backend/QA xác nhận cùng bundle chạy qua predictor dịch vụ
      (P0 trong [gate tuần 3](week-3-gate.md)).
- [ ] **Test đủ lớp và nhóm.** QA xác nhận từ số đếm tổng hợp rằng Test có cả `fake` và
      `real`, không có nhóm nào nằm ở nhiều split.
- [ ] **Artifact demo trỏ đúng bản khóa.** Backend đặt `MODEL_ARTIFACT_PATH` tới
      `backend/artifacts/multimodal` và `MODEL_METADATA_SHA256` bằng `metadata_sha256` của
      Multimodal trong hồ sơ.
- [ ] **Trạng thái `frozen` cho bundle.** Backend production chỉ nhận bundle có
      `status: frozen`. Đổi trạng thái sẽ làm đổi hash `metadata.json`, nên ML và BACKEND cần
      thống nhất đổi trước lần `collect` cuối. Hồ sơ sẽ ghim đúng bản demo dùng.
- [ ] **Không refit Train+Val.** Protocol ghi `refit_on_train_and_validation: false` và mọi
      bundle ghi `fit_split: train`.

## Trình tự ký

1. Integration khóa protocol. DATA/QA chốt split.
2. ML chạy lại Train/Val trên đúng config và split đã chốt, ghi `selected-models.json` mới,
   rồi export với `--expect-selected` và chạy parity.
3. ML chạy `collect` (lệnh dưới). Hồ sơ không còn blocker, commit qua PR.
4. ML ký, QA kiểm danh sách trên rồi ký. Hai chữ ký phải cùng `record_sha256`.
5. #50 chạy `verify` rồi chấm Test đúng một lần.

```sh
H=data/private/ml-v2/train-validation
.venv/bin/python -m ml.freeze collect --bundle-root backend/artifacts \
    --manifest $H/manifest.jsonl --split $H/split.csv --out release/model-freeze.json --replace
.venv/bin/python -m ml.freeze verify --bundle-root backend/artifacts --allow-unsigned
.venv/bin/python -m ml.freeze sign --role ml --by <github-login>
.venv/bin/python -m ml.freeze sign --role qa --by <github-login> --note "<bằng chứng đã kiểm>"
.venv/bin/python -m ml.freeze verify --bundle-root backend/artifacts
```

`collect` trả mã 2 khi còn blocker. `sign` từ chối khi còn blocker hoặc khi hai người ký hai
phiên bản khác nhau. `verify` trả mã 1 nếu thiếu chữ ký hoặc có file đã đổi sau freeze.
