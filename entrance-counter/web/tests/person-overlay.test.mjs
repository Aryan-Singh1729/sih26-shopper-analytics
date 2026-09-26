import assert from 'node:assert/strict';
import test from 'node:test';
import { personOverlayModel, personDetectionCopy } from '../person-overlay.mjs';

test('live overlay expires capture-aged boxes and rejects future sequences', () => {
  const status = { counter_running: true, stream_available: true, detection: {
    result_at: '2026-09-25T20:00:00.000Z', captured_at: 100, frame_sequence: 7,
    image_size: [1280, 720], boxes: [{ class: 'person', xyxy: [320, 72, 640, 648], confidence: 0.9 }],
  }};
  assert.equal(personOverlayModel(status, { sequence: 8, capturedAt: 100.3 }, 100300).length, 1);
  assert.equal(personOverlayModel(status, { sequence: 8, capturedAt: 100.6 }, 100600).length, 0);
  assert.equal(personOverlayModel(status, { sequence: 6, capturedAt: 100.1 }, 100100).length, 0);
});

test('positions a complete person box on a 1280 by 720 camera view', () => {
  const result = personOverlayModel({
    counter_running: true,
    stream_available: true,
    detection: {
      result_at: '2026-09-25T20:00:00.000Z',
      image_size: [1280, 720],
      boxes: [{ class: 'person', xyxy: [320, 72, 640, 648], confidence: 0.83 }],
    },
  }, Date.parse('2026-09-25T20:00:02.000Z'));
  assert.deepEqual(result, [{ left: 25, top: 10, width: 25, height: 80, label: 'PERSON 83%' }]);
});

test('uses person wording for zero, one, and multiple detections', () => {
  assert.equal(personDetectionCopy(0).pill, 'NO PERSON IN LATEST RESULT');
  assert.equal(personDetectionCopy(1).pill, '1 PERSON DETECTED');
  assert.equal(personDetectionCopy(2).pill, '2 PERSONS DETECTED');
});

test('hides stale, disconnected, and non-person boxes', () => {
  const status = {
    counter_running: true,
    stream_available: true,
    detection: {
      result_at: '2026-09-25T20:00:00.000Z',
      image_size: [1280, 720],
      boxes: [{ class: 'head', xyxy: [100, 100, 200, 200], confidence: 0.9 }],
    },
  };
  const now = Date.parse('2026-09-25T20:00:01.000Z');
  assert.equal(personOverlayModel(status, now).length, 0);
  assert.equal(personOverlayModel({ ...status, stream_available: false }, now).length, 0);
  assert.equal(personOverlayModel({ ...status, detection: { ...status.detection, boxes: [{ class: 'person', xyxy: [100, 100, 200, 200], confidence: 0.9 }] } }, now + 6000).length, 0);
});
