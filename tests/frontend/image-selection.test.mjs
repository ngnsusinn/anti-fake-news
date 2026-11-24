import assert from 'node:assert/strict';
import test from 'node:test';
import { candidateImageUrl } from '../../extension/modules/image-selection.js';

test('candidate downloads constrain loopback to the exact origin of the source tab', () => {
  const localImage = 'http://127.0.0.1:8765/fixture.png';
  assert.equal(candidateImageUrl(localImage, 'http://127.0.0.1:8765/article').href, localImage);
  for (const source of [null, 'https://article.example/story', 'http://127.0.0.1:9000/article']) {
    assert.throws(() => candidateImageUrl(localImage, source), /cùng origin/u);
  }
});

test('web candidates use HTTP(S) without embedded credentials', () => {
  assert.equal(candidateImageUrl('https://cdn.example/image.png', 'https://article.example/').hostname, 'cdn.example');
  assert.throws(() => candidateImageUrl('file:///image.png', 'https://article.example/'));
  assert.throws(() => candidateImageUrl('https://fixture:fixture@cdn.example/image', 'https://article.example/'));
});
