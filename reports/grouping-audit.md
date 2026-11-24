# AFN-017 · Audit gom nhóm

Trạng thái: chờ manifest đã đối soát từ AFN-016 và QA duyệt các quan hệ trên batch thật.

```sh
python -m scripts.group_samples --manifest data/private/afn-016-v1/manifest.jsonl \
  --manifest-sha256 <sha256-tu-validation.json> --image-root /private/images \
  --out data/private/afn-017-v1
```

Lệnh dùng môi trường Backend, ML và `jsonschema` như AFN-016. Tất cả mẫu accepted
được kiểm tra lại ảnh và checksum. Đầu ra nội bộ gồm `groups.json` với mỗi ID thuộc
đúng một thành phần liên thông, và `grouping-audit.json` với phiên bản quy tắc,
hash đầu vào/đầu ra, kích thước từng nhóm, ID các cặp làm phát sinh quan hệ, và
danh sách ứng viên event để rà thủ công.

Quan hệ gồm nhà xuất bản đã đối soát, event, URL đã bỏ tham số theo dõi, SHA-256
thân bài chuẩn hóa và file ảnh, cùng ngưỡng TF-IDF và pHash trong script.
Gom toàn bộ quan hệ bắc cầu thành một nhóm. Thiếu event metadata được đếm riêng.
Các ngưỡng tự động cần được QA duyệt trên mẫu thật. Rà nhóm lớn, ứng viên sự kiện,
ảnh gần trùng và các trường hợp nối hai nhãn. Ghi giải thích khi dữ liệu nguồn
không đủ để loại trừ mối quan hệ. Bàn giao hash mapping đã duyệt cho AFN-018.
