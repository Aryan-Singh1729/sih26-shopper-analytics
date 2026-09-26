import test from 'node:test';
import assert from 'node:assert/strict';
import { MjpegParser } from '../mjpeg.mjs';

test('parses a JPEG and timing across split network chunks', () => {
  const parser = new MjpegParser();
  const header = new TextEncoder().encode('--frame\r\nContent-Length: 3\r\nX-Frame-Sequence: 7\r\nX-Captured-At: 100\r\n\r\n');
  assert.deepEqual(parser.push(header.slice(0, 20)), []);
  assert.deepEqual(parser.push(header.slice(20)), []);
  const frames = parser.push(new Uint8Array([1, 2, 3, 13, 10]));
  assert.equal(frames.length, 1);
  assert.equal(frames[0].sequence, 7);
  assert.equal(frames[0].capturedAt, 100);
  assert.deepEqual([...frames[0].jpeg], [1, 2, 3]);
});
