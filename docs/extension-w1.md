# Extension tuần 1 · AFN-010 và AFN-011

## Chạy thử

1. Mở `chrome://extensions`, bật **Developer mode**, chọn **Load unpacked** và trỏ vào thư mục `extension`.
2. Từ gốc repo, chạy `python -m http.server 8765 --bind 127.0.0.1 --directory tests/fixtures/pages`. Mở `http://127.0.0.1:8765/article.html` rồi bấm **Anti Fake News**. Trang phân tích hiện nguồn, tiêu đề, thân bài có thể chỉnh sửa và URL ảnh tìm thấy.
3. Mở `dynamic.html` trước và sau khi bấm **Hiện bài mẫu**. Mở lại tiện ích sau khi nội dung xuất hiện để lấy ảnh chụp DOM mới. Thử trên `chrome://version/` để xem đường nhập thủ công khi không đọc được tab nguồn.

Mẫu bài và ảnh trong `tests/fixtures/pages` được tạo cho kiểm thử. Chức năng tuần 1 chạy độc lập với backend.

## Hợp đồng phiên

Worker tạo UUID mới mỗi lần bấm, truyền qua `analyze.html?session=<id>`, rồi trang đọc bản ghi `analysis:<id>` qua `readSession(location.search)` trong `modules/session.js`. Schema v1 gồm các trường sau.

| Trường | Giá trị |
| --- | --- |
| `version`, `id`, `tabId` | Phiên bản DTO, UUID phiên và ID tab nguồn nếu có |
| `url` | URL HTTP(S) của tab nguồn, hoặc `null` |
| `title`, `text` | Tiêu đề và văn bản trích xuất |
| `candidateImages` | Tối đa 12 mục có `url` tuyệt đối và `label` |
| `extraction` | `dom` khi lấy được văn bản, `empty` khi không thấy thân bài, `unavailable` khi không đọc được tab |

Phiên được xóa khi đóng tab phân tích. Nội dung chỉnh sửa ở giao diện tuần 1 chỉ nằm trong trang đang mở. Nguồn và URL ứng viên được trình bày như văn bản. Bộ trích ưu tiên vùng bài, bỏ các khối điều hướng, quảng cáo đánh dấu bằng `aside`, chân trang và nội dung ẩn. Trang có cấu trúc khác có thể cần nhập tay.

## Bằng chứng cục bộ

| Issue | Kiểm thử đạt |
| --- | --- |
| [AFN-010](https://github.com/ngnsusinn/anti-fake-news/issues/10) | Mở từng phiên qua action, lặp lại trên cùng tab, tách phiên giữa các tab, từ chối DOM sau khi tab đổi URL, nhập tay trên tab bị giới hạn và xóa bản ghi khi đóng. |
| [AFN-011](https://github.com/ngnsusinn/anti-fake-news/issues/11) | Trích từ trang bài mẫu, lọc khối phụ, phân giải ảnh tương đối, xử lý trang rỗng và bắt được nội dung sau khi DOM động cập nhật. |

```powershell
node --test tests/frontend/session.test.mjs

$playwrightDir = Join-Path ([IO.Path]::GetTempPath()) 'afn-extension-playwright'
npm install --prefix $playwrightDir playwright --no-audit --no-fund
& (Join-Path $playwrightDir 'node_modules/.bin/playwright.cmd') install chromium
$env:AFN_PLAYWRIGHT_PATH = Join-Path $playwrightDir 'node_modules/playwright'
node tests/frontend/browser-smoke.mjs
```

Browser smoke tải trực tiếp thư mục `extension` vào Chromium và dùng DevTools để kích hoạt action ở từng tab. QA review của `dangnguyen0512` vẫn đang chờ. [Tài liệu về thao tác kích hoạt action trong Chrome](https://pptr.dev/guides/chrome-extensions#triggering-extension-action).
