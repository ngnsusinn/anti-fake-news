# Biên bản trước khi mở Test · AFN-049

**26/11/2026 · ML và QA đã ký cùng một hồ sơ. Test chờ hồ sơ được merge.** Biên bản này đi kèm hồ sơ
[`release/model-freeze.json`](../release/model-freeze.json) (schema `afn-model-freeze-v1`,
`record_sha256` `7afd69de…`). #50 chỉ chạy khi hồ sơ có đủ chữ ký ML và QA, và
`ml.freeze verify` khớp với các file trên đĩa.

## Bản khóa

| Mục | Giá trị |
| --- | --- |
| Dữ liệu | Split `ml-v2`, nhóm chọn ngày 26/11/2026. Manifest Train/Val `a42af272…`, split đã ẩn ID Test `81058045…`. 153 Train / 32 Val / 33 Test khóa |
| Protocol | `configs/experiment.yaml` `dd4da7bd…`, `status: locked` (#111) |
| Lựa chọn | `configs/selected-models.json`, run `20261126T024649Z`, chọn trên Validation |
| Text-only | `text-only-20261126-275718e3163b`, C = 10, ngưỡng 0,60, Macro-F1 Val 0,686 |
| Image-only | `image-only-20261126-cd863cbaabf5`, C = 10, ngưỡng 0,30, Macro-F1 Val 0,536 |
| Multimodal | `multimodal-20261126-105d5f14e79a`, C = 100, ngưỡng 0,70, Macro-F1 Val 0,624 |
| `metadata.json` Multimodal | `6cd766a982015fb661f7eee8a5aa1317f05efc562769f8a13ba054e572fc09d5` |
| Nhãn | `{"0": "real", "1": "fake"}`, lớp dương `fake`, dự đoán `fake` khi điểm `>=` ngưỡng |
| Lệnh Test | `ml.evaluate_test`, nằm trong snapshot mã của hồ sơ |

Khóa protocol làm đổi hash config, nên ML đã chạy lại Train/Val. Lượt `20261126T024649Z`
cho cùng C, ngưỡng và Macro-F1 với lượt `20261125T145232Z`. Mảng trọng số của bundle
cũng không đổi: phần hash trong model version giữ nguyên, chỉ ngày thay đổi.

## Điều kiện và bằng chứng

- [x] **Protocol đã khóa.** #111. Giá trị không đổi so với bản `proposed`, chỉ đổi trạng thái.
- [x] **Split.** Nhóm chọn `ml-v2`. Kiểm tra của QA đều đạt: hash khớp, không có nhóm nào
      nằm ở nhiều split, không trùng ảnh/body/tiêu đề giữa Train và Val, Test đủ hai lớp
      ([audit #29](leakage-audit.md)).
      **Giới hạn đã biết:** 21 hostname publisher (theo bản đề xuất của QA) xuất hiện ở nhiều
      split, và chưa có event ID. Kết quả Test có thể cao hơn thực tế vì mô hình đã gặp cùng
      nguồn báo. Báo cáo #50/#51 phải ghi rõ giới hạn này.
- [x] **Chưa dùng Test để chọn cấu hình.** `selected-models.json` ghi `test_split.loaded: false`.
      Audit #29 đã xếp lại độc lập lưới tham số và khớp với C/ngưỡng đã chọn.
- [x] **Parity.** Chạy trên 32 mẫu Validation với bundle cuối: ba cấu hình đều PASS, max |Δ| = 0,
      cả với predictor tham chiếu (`ml.inference_parity`) lẫn `BundlePredictor` của Backend (#37).
- [x] **Không refit Train+Val.** `refit_on_train_and_validation: false`. Mọi bundle ghi `fit_split: train`.
- [x] **Mã đã commit.** Hồ sơ không còn blocker.
- [x] **Artifact demo trỏ đúng bản khóa.** Smoke Backend production offline dùng
      `AFN_MODEL_METADATA_SHA256` như bảng trên và `AFN_ALLOW_CANDIDATE_MODEL=true`.
      `GET /health` trả 200 real/ready, POST thiếu token trả 401 và POST hợp lệ trên
      đầu vào tổng hợp trả 200 với đúng model ID/version. Bundle giữ `status: candidate`
      để giữ nguyên hash đã ký. Diễn tập Chromium thuộc phạm vi #43.
- [x] **QA ký.** `dangnguyen0512` xác nhận hồ sơ ngày 26/11/2026. QA đối chiếu 13/13
      SHA-256 của ba bundle, hash manifest Train/Validation và split đã ẩn Test ID,
      cùng các tệp mã/cấu hình đã ghim. `ml.freeze verify` trả mã 0 trước và sau
      khi ký. Cả hai chữ ký có cùng canonical record hash.
      [Bằng chứng QA](https://github.com/ngnsusinn/anti-fake-news/pull/119)

## Bàn giao bundle

Theo [hướng dẫn artifact](../backend/artifacts/README.md), bundle không nằm trong git. ML gửi
nguyên thư mục `backend/artifacts/` (khoảng 360 KB). Người nhận đặt thư mục vào đúng vị trí
rồi chạy `verify`. Lệnh trả mã 0 nghĩa là bundle trùng từng byte với bản khóa.

## Lệnh

```sh
# QA: kiểm hash trước khi ký (hồ sơ chưa ký thì dùng --allow-unsigned)
.venv/bin/python -m ml.freeze verify --bundle-root backend/artifacts --allow-unsigned
.venv/bin/python -m ml.freeze sign --role qa --by <github-login> --note "<bằng chứng đã kiểm>"
.venv/bin/python -m ml.freeze verify --bundle-root backend/artifacts   # phải trả mã 0
```

Chữ ký QA chỉ thêm vào khối `signoffs` nên không làm đổi `record_sha256`. Nếu QA cần sửa bất
kỳ trường nào khác, ML phải chạy lại `collect` và cả hai ký lại. Sau khi hồ sơ có đủ hai chữ
ký và đã merge, ML chạy #50 đúng một lần.
