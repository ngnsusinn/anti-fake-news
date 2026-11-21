import { readSession } from './modules/session.js';

const get = id => document.getElementById(id);
const session = await readSession(location.search).catch(() => null);
const extractionMessages = {
  dom: 'Rà lại văn bản đã lấy từ trang. Bạn có thể chỉnh sửa bên dưới.',
  empty: 'Chưa tìm thấy nội dung bài viết. Bạn có thể nhập hoặc dán văn bản, hoặc mở lại tiện ích khi bài đã tải xong.',
  unavailable: 'Không đọc được tab nguồn. Bạn có thể nhập hoặc dán văn bản bên dưới.',
};

get('extraction').textContent = extractionMessages[session?.extraction]
  ?? 'Chưa có phiên nguồn. Bạn có thể nhập hoặc dán văn bản bên dưới.';

if (session?.url) {
  const source = get('source');
  source.textContent = 'Nguồn: ' + session.url;
  source.hidden = false;
}
get('title').value = session?.title ?? '';
get('text').value = session?.text ?? '';

const candidates = session?.candidateImages ?? [];
if (candidates.length) {
  const list = get('candidates');
  for (const { url, label } of candidates) {
    const item = document.createElement('li');
    item.textContent = label ? label + ' · ' + url : url;
    list.append(item);
  }
  get('image-candidates').hidden = false;
}
get('draft').disabled = false;
