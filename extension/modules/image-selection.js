const MAX_BYTES = 10 * 1024 * 1024;
const MAX_PIXELS = 20_000_000;
const PNG_PREFIX = [137, 80, 78, 71, 13, 10, 26, 10];

function imageHeader(buffer) {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  if (bytes.length >= 33 && PNG_PREFIX.every((value, index) => bytes[index] === value)
      && view.getUint32(8) === 13 && view.getUint32(12) === 0x49484452) {
    return { type: 'image/png', width: view.getUint32(16), height: view.getUint32(20) };
  }
  if (bytes[0] !== 255 || bytes[1] !== 216) return null;
  let offset = 2;
  while (offset + 3 < bytes.length && bytes[offset++] === 255) {
    while (bytes[offset] === 255) offset++;
    const marker = bytes[offset++];
    if (marker === 0xda || marker === 0xd9 || offset + 2 > bytes.length) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    const size = view.getUint16(offset);
    if (size < 2 || offset + size > bytes.length) break;
    const isFrame = marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker);
    if (isFrame && size >= 8) {
      return { type: 'image/jpeg', width: view.getUint16(offset + 5), height: view.getUint16(offset + 3) };
    }
    offset += size;
  }
  return null;
}

async function validate(file) {
  if (file.size > MAX_BYTES) throw Error('Ảnh vượt giới hạn 10 MiB.');
  const header = imageHeader(await file.arrayBuffer());
  if (!header?.width || !header.height) throw Error('Chọn một ảnh JPEG hoặc PNG đọc được.');
  if (header.width * header.height > MAX_PIXELS) throw Error('Ảnh vượt giới hạn 20 megapixel.');
  if (file.type && file.type !== 'application/octet-stream' && file.type !== header.type) {
    throw Error('Định dạng khai báo không khớp nội dung ảnh.');
  }
  const name = file.name === 'article' ? (header.type === 'image/jpeg' ? 'article.jpg' : 'article.png') : file.name;
  const normalized = new File([file], name, { type: header.type });
  const bitmap = await createImageBitmap(normalized).catch(() => null);
  if (!bitmap) throw Error('Không giải mã được ảnh. Hãy chọn ảnh khác.');
  bitmap.close();
  return normalized;
}

export function candidateImageUrl(value, sourceUrl) {
  const url = new URL(value);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw Error();

  const loopback = url.hostname === 'localhost' || url.hostname === '[::1]'
    || /^127\.\d+\.\d+\.\d+$/u.test(url.hostname);
  if (loopback && (!sourceUrl || new URL(sourceUrl).origin !== url.origin)) {
    throw Error('Ảnh loopback phải cùng origin với tab nguồn.');
  }
  return url;
}

async function fetchCandidate(value, sourceUrl, controller) {
  const timeout = setTimeout(() => controller.abort(), 15_000);
  try {
    const url = candidateImageUrl(value, sourceUrl);
    const response = await fetch(url, {
      signal: controller.signal, credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error',
    });
    if (!response.ok || !response.body) throw Error();
    const reader = response.body.getReader();
    const chunks = [];
    let total = 0;
    for (;;) {
      const { done, value: chunk } = await reader.read();
      if (done) break;
      total += chunk.byteLength;
      if (total > MAX_BYTES) {
        await reader.cancel();
        throw Error();
      }
      chunks.push(chunk);
    }
    const type = response.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase() || '';
    return new File(chunks, 'article', { type });
  } catch {
    throw Error('Không tải được ảnh trang hoặc ảnh quá lớn. Hãy chọn ảnh khác hoặc tải tệp JPEG/PNG.');
  } finally {
    clearTimeout(timeout);
  }
}

export function createImageSelection(onChange) {
  let current;
  let file = null;
  let preview = null;

  function publish(next, status, message) {
    if (preview) URL.revokeObjectURL(preview);
    file = next;
    preview = file ? URL.createObjectURL(file) : null;
    onChange({ file, preview, status, message });
  }

  async function choose(load) {
    current?.abort();
    const operation = new AbortController();
    current = operation;
    publish(null, 'loading', 'Đang kiểm tra ảnh…');
    try {
      const selected = await load(operation);
      if (current !== operation) return;
      const next = await validate(selected);
      if (current === operation) publish(next, 'ready', 'Đã chọn ảnh: ' + next.name);
    } catch (error) {
      if (current === operation) publish(null, 'error', error.message);
    }
  }

  return {
    get file() { return file; },
    chooseCandidate: (url, sourceUrl) => choose(controller => fetchCandidate(url, sourceUrl, controller)),
    chooseFile: selected => selected && choose(() => selected),
    clear() {
      current?.abort();
      current = null;
      publish(null, 'idle', '');
    },
  };
}
