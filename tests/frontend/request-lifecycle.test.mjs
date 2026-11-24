import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequestLifecycle } from '../../extension/modules/request-lifecycle.js';

test('late completion cannot override a superseding generation', async () => {
  const lifecycle = createRequestLifecycle();
  let release;
  const displayed = [];
  const older = lifecycle.begin();
  const slow = new Promise(resolve => { release = resolve; }).then(id => {
    if (lifecycle.accepts(older, id)) displayed.push(id);
  });

  const current = lifecycle.begin();
  assert.ok(older.signal.aborted);
  assert.notEqual(current.id, older.id);
  assert.equal(lifecycle.accepts(current, older.id), false);
  assert.ok(lifecycle.accepts(current, current.id));
  displayed.push(current.id);
  lifecycle.finish(current);
  release(older.id);
  await slow;
  assert.deepEqual(displayed, [current.id]);
});

test('editing invalidates in-flight work and another tab remains independent', () => {
  const left = createRequestLifecycle(() => 'same-id');
  const right = createRequestLifecycle(() => 'same-id');
  const stale = left.begin();
  const otherTab = right.begin();
  left.invalidate();
  const retry = left.begin();
  assert.equal(left.accepts(stale, stale.id), false);
  assert.equal(left.accepts(otherTab, otherTab.id), false);
  assert.equal(right.accepts(otherTab, otherTab.id), true);
  assert.equal(left.accepts(retry, null), false);
  assert.equal(left.accepts(retry, retry.id), true);
});
