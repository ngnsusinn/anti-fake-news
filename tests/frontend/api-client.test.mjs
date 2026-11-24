import assert from 'node:assert/strict';
import test from 'node:test';
import { createApiClient } from '../../extension/modules/api-client.js';

const config = { endpoint: 'http://127.0.0.1:8000', demoToken: 'fixture-token', timeoutMs: 30_000 };
const draft = { title: 'Title', text: 'Body', image: new File(['fixture'], 'test.png', { type: 'image/png' }) };
const id = '550e8400-e29b-41d4-a716-446655440000';

test('predict sends multipart fields including an image file and lets fetch set the boundary', async () => {
  const client = createApiClient(async (url, init) => {
    assert.equal(url, 'http://127.0.0.1:8000/predict');
    assert.equal(init.method, 'POST');
    assert.deepEqual(init.headers, { 'X-Demo-Token': 'fixture-token' });
    assert.equal(init.body.get('request_id'), id);
    assert.equal(init.body.get('title'), 'Title');
    assert.equal(init.body.get('text'), 'Body');
    assert.equal(await init.body.get('image').text(), 'fixture');
    return Response.json({
      request_id: id, label: 'real', fake_score: 0.42, model_id: 'dev-mock-not-a-model',
      model_version: 'test', processing_time_ms: 2, text_truncated: false,
    }, { headers: { 'X-AFN-Inference-Mode': 'mock' } });
  });
  assert.equal((await client.predict(config, draft, id)).mode, 'mock');
});

test('rejects non-loopback endpoints before sending anything', async () => {
  const client = createApiClient(() => assert.fail('Must not forward a token or article'));
  for (const endpoint of ['https://example.test', 'http://127.0.0.1.evil.test', 'http://127.0.0.1:8000/other']) {
    await assert.rejects(client.predict({ ...config, endpoint }, draft, id), { kind: 'config' });
  }
});

test('health does not send a token and requires a valid contract', async () => {
  const client = createApiClient(async (url, init) => {
    assert.match(url, /\/health$/);
    assert.equal(init.headers, undefined);
    return Response.json({ service_status: 'ok', model_ready: false, contract_version: '0.1.1' });
  });
  assert.equal((await client.health(config)).data.model_ready, false);
  const broken = createApiClient(async () => Response.json({ hello: 'world' }));
  await assert.rejects(broken.health(config), { kind: 'invalid-response' });
});
