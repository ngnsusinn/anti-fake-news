# AFN-016 · Xác thực manifest

Trạng thái: chờ gói đối soát AFN-003 và nghiệm thu QA trên batch thật.

## Chạy kiểm tra

1. Đối chiếu snapshot và SHA-256 theo
   [bàn giao AFN-003](recovery-summary.md#bàn-giao-bằng-chứng-cho-qa-và-afn-016).
2. DATA ghi một quyết định theo [schema AFN-001](../data/manifest.schema.json) cho
   mỗi ID trong inventory. Kiểm tra bài tiếng Anh, đúng bài và đúng ngữ cảnh ảnh,
   nguồn nhãn và quyền cho cả bài lẫn ảnh. Giữ trạng thái `pending` khi chưa rõ.
   Nếu loại mẫu, ghi `exclusion_reason`. Kết quả mô hình không dùng để quyết định.
3. Với môi trường Backend của repo, cài thêm `jsonschema==4.26.0` rồi chạy:

```sh
python -m scripts.validate_manifest --decisions /private/decisions.jsonl \
  --snapshot /private/valid-400.jsonl --snapshot-sha256 <sha256-tu-ban-giao> \
  --image-root /private/images --out data/private/afn-016-v1
```

Validator kiểm tra đủ ID theo snapshot, khóa không trùng và khớp nguồn/nhãn,
quyền sử dụng của mẫu accepted và khả năng xử lý thân bài. Với ảnh accepted,
kiểm tra SHA-256, định dạng, giới hạn byte/pixel và giải mã bằng tiền xử lý dùng chung.
Đầu ra riêng tư gồm `manifest.jsonl` theo schema và `validation.json` chứa số lượng
trước/sau, lý do loại và checksum. Bàn giao checksum cho AFN-017 sau khi QA xác nhận.

Số liệu từ bản 352 dòng trước đây là số liệu khảo sát. Cần inventory và đối soát
quyền từ DATA để xác nhận đủ mẫu và nguyên nhân loại trên batch AFN-003.
