import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.AFN_PLAYWRIGHT_PATH || 'playwright');
const root = fileURLToPath(new URL('../../', import.meta.url));
const fixtures = join(root, 'tests', 'fixtures', 'pages');
const extension = join(root, 'extension');
const profile = await mkdtemp(join(tmpdir(), 'afn-w1-browser-'));

const mediaTypes = new Map([
  ['/article.html', 'text/html; charset=UTF-8'],
  ['/dynamic.html', 'text/html; charset=UTF-8'],
  ['/dynamic.js', 'text/javascript'],
  ['/synthetic.png', 'image/png'],
]);
const server = createServer(async (request, response) => {
  const mediaType = mediaTypes.get(request.url);
  if (!mediaType) {
    response.writeHead(404).end();
    return;
  }
  try {
    const content = await readFile(join(fixtures, request.url.slice(1)));
    response.writeHead(200, { 'Content-Type': mediaType }).end(content);
  } catch {
    response.writeHead(500).end();
  }
});
let context;

try {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const origin = 'http://127.0.0.1:' + server.address().port;
  const manifest = JSON.parse(await readFile(join(extension, 'manifest.json'), 'utf8'));
  assert.deepEqual(manifest.permissions, ['activeTab', 'scripting', 'storage']);
  assert.equal(manifest.host_permissions, undefined);
  context = await chromium.launchPersistentContext(profile, {
    channel: 'chromium',
    args: [
      '--enable-unsafe-extension-debugging',
      '--disable-extensions-except=' + extension,
      '--load-extension=' + extension,
    ],
  });
  context.setDefaultTimeout(7000);
  const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker');
  const extensionId = new URL(worker.url()).hostname;
  const browserSession = await context.browser().newBrowserCDPSession();

  async function openAnalysis(source) {
    await source.bringToFront();
    const { targetInfos } = await browserSession.send('Target.getTargets', {
      filter: [{ type: 'tab' }, { exclude: true }],
    });
    const tab = targetInfos.find(target => target.url === source.url());
    assert.ok(tab, 'Chrome tab target for ' + source.url());
    const [page] = await Promise.all([
      context.waitForEvent('page'),
      browserSession.send('Extensions.triggerAction', { id: extensionId, targetId: tab.targetId }),
    ]);
    await page.waitForFunction(() => document.querySelector('#draft')?.disabled === false);
    return page;
  }

  function sessionId(page) {
    return new URL(page.url()).searchParams.get('session');
  }

  const article = await context.newPage();
  await article.goto(origin + '/article.html');
  const analysis = await openAnalysis(article);
  assert.match(await analysis.locator('#title').inputValue(), /Vườn cộng đồng/u);
  const input = await analysis.locator('#text').inputValue();
  assert.match(input, /hạt giống/u);
  assert.doesNotMatch(input, /Menu|Quảng cáo|Nội dung ẩn|chân trang/u);
  assert.match(await analysis.locator('#source').innerText(), /article\.html/u);
  assert.equal(await analysis.locator('#candidates li').count(), 2);
  assert.match(await analysis.locator('#candidates li').first().innerText(), /\/synthetic\.png/u);
  console.log('PASS article DOM, relative images, filtering and activeTab permission');

  const dynamic = await context.newPage();
  await dynamic.goto(origin + '/dynamic.html');
  const empty = await openAnalysis(dynamic);
  assert.match(await empty.locator('#extraction').innerText(), /Chưa tìm thấy/u);
  assert.equal(await empty.locator('#text').inputValue(), '');
  await empty.locator('#text').fill('Bản nháp nhập tay.');
  await dynamic.locator('button').click();
  const loaded = await openAnalysis(dynamic);
  assert.notEqual(sessionId(empty), sessionId(loaded));
  assert.match(await loaded.locator('#text').inputValue(), /xuất hiện sau/u);
  assert.equal(await empty.locator('#text').inputValue(), 'Bản nháp nhập tay.');
  assert.equal(await analysis.locator('#text').inputValue(), input);
  console.log('PASS empty/dynamic DOM, manual entry and isolated sessions');

  const restricted = await context.newPage();
  await restricted.goto('chrome://version/');
  const manual = await openAnalysis(restricted);
  assert.match(await manual.locator('#extraction').innerText(), /Không đọc được tab nguồn/u);
  await manual.locator('#text').fill('Nội dung khi không có quyền đọc tab.');
  assert.equal(await manual.locator('#text').inputValue(), 'Nội dung khi không có quyền đọc tab.');

  const key = 'analysis:' + sessionId(analysis);
  await analysis.close();
  let stored = true;
  for (let attempt = 0; stored && attempt < 20; attempt++) {
    stored = await worker.evaluate(async id => Boolean((await chrome.storage.session.get(id))[id]), key);
    if (stored) await delay(50);
  }
  assert.equal(stored, false);
  assert.match(await loaded.locator('#text').inputValue(), /xuất hiện sau/u);
  console.log('PASS restricted tab fallback and session cleanup');
} finally {
  await context?.close();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
  await rm(profile, { recursive: true, force: true });
}
