import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError, createApiClient } from '../../extension/modules/api-client.js';
import { bindErrorRecovery, describeApiError } from '../../extension/modules/error-recovery.js';

test('maps supported HTTP responses and client errors without displaying server details', () => {
  for (const status of [400, 401, 403, 413, 503]) {
    const message = describeApiError(new ApiError('http', { status, code: 'private input' }));
    assert.doesNotMatch(message, /private input/);
    assert.ok(message.length > 30);
  }
  assert.match(describeApiError(new ApiError('invalid-response')), /không hợp lệ/u);
  assert.match(describeApiError(new ApiError('timeout')), /Backend có thể vẫn đang xử lý/u);
});

test('manual retry is bound to the failed operation and cleared before reuse', () => {
  const status = { textContent: '' };
  const button = Object.assign(new EventTarget(), { hidden: true });
  const recovery = bindErrorRecovery(status, button);
  let retries = 0;
  recovery.show(new ApiError('http', { status: 401 }), () => { retries++; });
  assert.match(status.textContent, /token/u);
  assert.equal(button.hidden, false);
  assert.equal(recovery.hasRetry, true);
  button.dispatchEvent(new Event('click'));
  assert.equal(retries, 1);
  recovery.clear();
  button.dispatchEvent(new Event('click'));
  assert.equal(button.hidden, true);
  assert.equal(recovery.hasRetry, false);
  assert.equal(retries, 1);
});

test('client reports a timeout separately from invalid response and connection failures', async () => {
  const config = { endpoint: 'http://127.0.0.1:8000', demoToken: '', timeoutMs: 1000 };
  const slow = createApiClient((_url, { signal }) => new Promise((_, reject) => {
    signal.addEventListener('abort', () => reject(Error('aborted')), { once: true });
  }));
  await assert.rejects(slow.health(config), { kind: 'timeout' });
  const gone = createApiClient(async () => { throw Error('fetch failed'); });
  await assert.rejects(gone.health(config), { kind: 'network' });
  const broken = createApiClient(async () => new Response('broken'));
  await assert.rejects(broken.health(config), { kind: 'invalid-response' });
});
