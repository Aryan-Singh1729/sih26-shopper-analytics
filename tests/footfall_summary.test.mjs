import test from 'node:test';
import assert from 'node:assert/strict';
import {displayClock, displaySummary} from '../footfall-web/summary.mjs';

const date = new Date('2026-09-26T10:00:00Z'); // 15:30 in India
const hourly = Array.from({length: 24}, (_, hour) => ({hour, arrivals: hour === 14 ? 8 : hour === 15 ? 3 : 0}));

test('display cards report todays total, current hour, and busiest hour', () => {
  const result = displaySummary({date: '2026-09-26', total_arrivals: 11, hourly, peak_hours: [14], peak_count: 8}, date);
  assert.deepEqual(result, {
    total: 11,
    current: 3,
    currentDetail: '15:00–16:00 today',
    peak: '14:00–15:00',
    peakDetail: '8 arrivals',
  });
});

test('a past date does not pretend to have current-hour arrivals', () => {
  const result = displaySummary({date: '2026-09-25', total_arrivals: 0, hourly: Array.from({length: 24}, (_, hour) => ({hour, arrivals: 0})), peak_hours: [], peak_count: 0}, date);
  assert.equal(result.total, 0);
  assert.equal(result.current, '—');
  assert.equal(result.currentDetail, 'Select today to see the current hour');
  assert.equal(result.peak, 'No arrivals');
  assert.equal(result.peakDetail, '0 arrivals');
});

test('display clock uses compact 24-hour India time on narrow side card', () => {
  const result = displayClock(date);
  assert.equal(result.time, '15:30:00');
  assert.equal(result.date, 'Saturday, 26 Sept 2026');
});
