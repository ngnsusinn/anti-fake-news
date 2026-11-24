# AFN-018 · Chia nhóm 70/15/15 và bàn giao dataset

Trạng thái: chờ AFN-017 bàn giao mapping và hash đã được QA duyệt.
Các file của lần pilot cũ không dùng để khóa tập nghiên cứu.

```sh
python -m scripts.split_data --manifest data/private/afn-016-v1/manifest.jsonl \
  --groups data/private/afn-017-v1/groups.json --groups-sha256 <sha256-duyet-boi-QA> \
  --audit data/private/afn-017-v1/grouping-audit.json --image-root /private/images \
  --out data/private/afn-018-v1 --version v1
```

Script kiểm tra hash và phạm vi mapping, rồi kiểm tra lại quan hệ trùng chính xác và
các cạnh audit. Seed 42 phân bổ các nhóm nguyên vẹn, cân bằng tỷ lệ mục tiêu và
phân bố nguồn/nhãn. Script dừng nếu không tìm được ba tập có dữ liệu với đủ hai
nhãn ở Train. Báo cáo riêng ghi độ lệch, số lượng, nhãn còn thiếu và SHA-256.
Khi cần chỉnh dữ liệu, chọn phiên bản và thư mục mới.

- Giữ cả thư mục đầu ra trong vùng riêng do QA quản lý.
- Chỉ chia sẻ thư mục `train-validation/` với ML trước AFN-049. Đọc
  `manifest.jsonl`, `split.csv` và dùng `--image-root <train-validation>/images`.
  Dòng Test trong CSV chỉ có split và group ID trung tính. Thư mục này chỉ chứa
  bài và ảnh Train/Validation.
- `qa-only/` chứa đầy đủ phân công, ảnh Test và báo cáo.
  `train.json`, `validation.json`, `test.json` là các danh sách ID cho QA.
  Dùng manifest/CSV đầy đủ với `--image-root <qa-only>/images` trong luồng chỉ
  đọc Test sau khi AFN-049 ký freeze.
- QA kiểm tra độc lập khóa nhóm, các trường hợp thiếu nguồn/event, độ phân tán
  nhóm/lớp và hash của file bàn giao. Nếu quá ít nhóm hoặc thiếu lớp để đánh
  giá, ghi blocker và giữ nguyên nhóm.
