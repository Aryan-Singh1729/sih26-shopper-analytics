import test from 'node:test';
import assert from 'node:assert/strict';

test('a slow renderer takes only the newest queued camera frame', async () => {
  let LatestFrameSlot;
  try { ({LatestFrameSlot} = await import('../footfall-web/latest-frame.mjs')); } catch {}
  assert.equal(typeof LatestFrameSlot, 'function');
  const slot = new LatestFrameSlot();
  slot.push({sequence: 41});
  slot.push({sequence: 42});
  slot.push({sequence: 43});
  assert.equal(slot.take()?.sequence, 43);
  assert.equal(slot.take(), null);
});
