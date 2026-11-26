# Pipeline ML ba cấu hình — AFN-019 / AFN-020 / AFN-021

Trạng thái: **đã chạy end-to-end trên fixture tổng hợp**, chờ BACKEND review. Chưa chạy trên
dữ liệu nghiên cứu: phần đó thuộc #34, sau khi DATA chốt split (#18) và QA audit (#29).
Mọi điểm số trên fixture chỉ là smoke test (`evidence_kind: FIXTURE_SMOKE_NOT_RESEARCH`),
**không** được đưa vào báo cáo như kết quả nghiên cứu.

## Đầu vào

| Đầu vào | Dạng | Ghi chú |
| --- | --- | --- |
| Manifest | JSONL `afn-manifest-v1` ([data-contract.md](data-contract.md)) | Chỉ chứa payload Train/Validation đã `accepted` |
| Split audit | CSV có đúng ba cột `sample_id,split,group_id` | Đề xuất giao diện cho DATA #18. Mỗi mẫu Test chỉ có `split=test` và group ID không chứa nhãn; để trống `sample_id`. |
| Ảnh | `image.path` tương đối so với `--image-root` (mặc định là thư mục chứa manifest) | SHA-256 được đối chiếu với manifest |
| Tham số | [`configs/experiment.yaml`](../configs/experiment.yaml) | Protocol AFN-004 + khối `text_features`, `image_features`, `fusion` |

Loader đối chiếu tập ID giữa manifest và các dòng split có ID, kiểm tra trạng thái accepted,
nhãn hợp lệ và group ID khớp trên từng mẫu. Mọi dòng split phải có group ID đã audit.
Loader phát hiện group xuất hiện ở nhiều split, kể cả group của các dòng Test đã ẩn ID.

## Khóa tập Test

- Trước khi #49 duyệt freeze, DATA bàn giao manifest chỉ chứa Train/Validation, ảnh tương ứng và
  CSV audit đã ẩn ID của Test. Khóa `source:label:source_id` có chứa nhãn nên cần giữ riêng cùng
  payload Test. Runner chỉ nhận đường dẫn của gói bàn giao này và đếm số mẫu Test từ CSV audit.
- Loader từ chối CSV có ID Test trước khi mở manifest. Sau #49, #50 có thể dùng manifest/split đã
  cấp quyền, yêu cầu split `test` và truyền `allow_test=True`.
- `ml.run_experiments` không có tùy chọn nào để mở Test và từ chối dataset có chứa Test.
  Chấm Test là lệnh riêng của #50, chỉ chạy sau khi #49 ký freeze ([working-agreement.md](working-agreement.md)).
- `ml.evaluate_test` (#50) chạy `ml.freeze verify` trước tiên. Lệnh dừng nếu hồ sơ
  [`release/model-freeze.json`](../release/model-freeze.json) thiếu chữ ký ML/QA, hoặc nếu
  manifest Train/Validation, split đã ẩn ID Test, config, mã hay bundle đã đổi.
  Sau đó lệnh đối chiếu split QA với split đã freeze (cùng
  Train/Val, cùng số dòng và group Test) rồi mới đọc manifest Test. Lệnh không fit gì, chỉ
  chấm qua `ModelBundle.predict`. Dùng cùng thư mục đầu ra của lần đánh giá đầu tiên. Nếu
  đã bắt đầu chấm, lệnh từ chối đọc lại Test khi thiếu `--rerun-reason`. Mỗi lượt có kết quả
  ghi thời gian, hash dự đoán và lý do chạy lại trong `test-metrics.json`. Nếu tiến trình bị
  buộc dừng và còn thư mục `.test-evaluation.lock`, xác nhận tiến trình cũ đã dừng trước khi
  gỡ khóa và ghi lý do lỗi kỹ thuật khi chạy lại.
- Chặn fit sai tập: TF-IDF và Logistic Regression chỉ fit trên Train (`FitOnNonTrainError`).
  Có test xác nhận mọi lần `fit` đều đúng bằng số dòng Train và không bao giờ refit trên Train+Val.

## Ba cấu hình

| Cấu hình | Đặc trưng | Mã |
| --- | --- | --- |
| Text-only | `preprocess_text` → TF-IDF (1,2), max_features 5000, min_df 2, sublinear_tf, L2 | `ml/train_text.py` |
| Image-only | `load_image_rgb` → CLIP ViT-B/32 đóng băng → L2 (512 chiều) | `ml/extract_embeddings.py`, `ml/train_image.py` |
| Multimodal | CSR `hstack([TF-IDF, CLIP])`, thứ tự text rồi image, float64 | `ml/train_multimodal.py` |

Cả ba dùng cùng split; runner kiểm tra cả ba có cùng hash thứ tự `sample_id` của Train/Validation.
Ghép đặc trưng yêu cầu hai khối có **cùng danh sách và cùng thứ tự** `sample_id`; lệch thì raise
`SampleOrderError` (không tự sắp xếp lại hay inner join).

**Chọn tham số** (theo protocol): với mỗi C, fit trên Train; với mỗi ngưỡng, `fake` nếu
P(fake) ≥ ngưỡng (tra qua `classes_`); Macro-F1 trên Validation làm tròn 12 chữ số; hòa thì
ưu tiên ngưỡng gần 0,5, rồi C nhỏ hơn, rồi ngưỡng thấp hơn. `liblinear`, L2, `class_weight=balanced`.
scikit-learn ≥ 1.8 bỏ dần `penalty`, nên `penalty: l2` được truyền tương đương bằng `l1_ratio=0`.
Cảnh báo không hội tụ được ghi lại theo từng C.

## Cache embedding

Khóa cache = SHA-256 của (SHA-256 ảnh, repo, revision, SHA-256 `preprocessor_config.json`,
`PREPROCESS_VERSION`, dtype). Đổi ảnh, checkpoint, processor hoặc tiền xử lý → khóa khác →
tính lại. Mỗi entry là một file `.npy`, ghi atomic, khi đọc kiểm tra lại shape/dtype/hữu hạn/norm;
entry hỏng sẽ bị bỏ qua và tính lại. Mặc định ở `cache/embeddings/` (đã gitignore).

## Lệnh chạy

```sh
# Dữ liệu thật (bản xuất DATA ở PR #87): lọc + gom nhóm lại + chia lại -> data/private/ml-v2
# Chi tiết và kết quả: reports/ml-train-validation.md
.venv/bin/python -m ml.prepare_dataset --manifest data/processed/manifest.json \
    --groups data/processed/groups.json --image-root data --out data/private/ml-v2

# Dữ liệu tổng hợp (manifest Train/Validation + split audit + ảnh PNG, is_fixture: true)
.venv/bin/python -m ml.fixtures --out cache/ml-fixture

# Ba cấu hình, chỉ Train/Validation
.venv/bin/python -m ml.run_experiments --manifest cache/ml-fixture/manifest.jsonl \
    --split cache/ml-fixture/split.csv --offline

# Từng phần
.venv/bin/python -m ml.train_text  --manifest M.jsonl --split S.csv
.venv/bin/python -m ml.train_image --manifest M.jsonl --split S.csv --image-root DIR --offline
.venv/bin/python -m ml.extract_embeddings --manifest M.jsonl --split S.csv --out cache/embeddings/run.npz --offline

# #50: một lượt Test cuối, chỉ sau khi #49 ký (Test-only manifest và split đầy đủ do QA giữ)
.venv/bin/python -m ml.evaluate_test --freeze release/model-freeze.json --bundle-root backend/artifacts \
    --locked-manifest data/private/ml-v2/train-validation/manifest.jsonl \
    --locked-split data/private/ml-v2/train-validation/split.csv \
    --manifest data/private/ml-v2/qa-only/manifest-test.jsonl --split data/private/ml-v2/qa-only/split.csv \
    --image-root data --offline --out-dir reports
# -> reports/test-predictions.jsonl, reports/test-metrics.json, reports/confusion-matrices/

# Test (fixture + encoder giả; thêm AFN_CLIP_TESTS=1 để chạy cả CLIP thật đã cache)
.venv/bin/python -m pytest -q tests/test_text_pipeline.py tests/test_image_pipeline.py tests/test_fusion.py
```

`run_experiments` ghi `cache/runs/<run-id>/results.json` gồm: config, hash manifest/split/config,
phiên bản thư viện, hash thứ tự mẫu, toàn bộ lưới C × ngưỡng, lựa chọn, cờ `evidence_kind`, và số dòng Test bị khóa.

## Kết quả smoke trên fixture (23/11/2026, macOS M1, CPU, CLIP thật)

Fixture: 28 Train, 8 Validation, 6 Test (bị khóa, không nạp).

| Cấu hình | Số chiều | Ghi chú |
| --- | --- | --- |
| Text-only | 391 | Từ vựng fit trên Train |
| Image-only | 512 | Khoảng 53 ms/ảnh khi encode; lần chạy 2 lấy 28/28 ảnh từ cache |
| Multimodal | 903 | = 391 + 512 |

Cả ba chọn C = 0,01, ngưỡng 0,5, Macro-F1 Validation = 1,0 **trên dữ liệu tổng hợp cố ý dễ**,
chỉ chứng minh pipeline chạy đúng, không nói gì về chất lượng mô hình.

## Bàn giao

- **Audit #29 (QA):** lệnh Train/Val là `ml.run_experiments` ở trên. Bằng chứng không rò rỉ:
  `tests/test_fusion.py::test_classifiers_are_fit_on_train_rows_only`, `tests/test_text_pipeline.py::test_test_split_is_locked`.
- **DATA #18:** xác nhận giao diện bàn giao manifest Train/Validation và CSV audit
  `sample_id,split,group_id`, kèm checksum. Test giữ riêng đến #49/#50.
- **#34:** chạy runner trên manifest/split thật sau audit; **#35:** lưu artifact (chưa làm ở đây).
- **Integration:** xác nhận khối `text_features` / `image_features` / `fusion` mới thêm vào `experiment.yaml`.
