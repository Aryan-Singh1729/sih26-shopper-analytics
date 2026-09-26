const zone = 'Asia/Calcutta';
const hourLabel = hour => `${String(hour).padStart(2, '0')}:00`;

export function displayClock(now = new Date()) {
  return {
    time: new Intl.DateTimeFormat('en-GB', {timeZone: zone, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'}).format(now),
    date: new Intl.DateTimeFormat('en-IN', {timeZone: zone, weekday: 'long', day: 'numeric', month: 'short', year: 'numeric'}).format(now),
  };
}

export function displaySummary(data, now = new Date()) {
  const today = new Intl.DateTimeFormat('en-CA', {timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit'}).format(now);
  const hour = Number(new Intl.DateTimeFormat('en-GB', {timeZone: zone, hour: '2-digit', hourCycle: 'h23'}).format(now));
  const peak = data.peak_hours[0];
  return {
    total: data.total_arrivals,
    current: data.date === today ? data.hourly[hour].arrivals : '—',
    currentDetail: data.date === today ? `${hourLabel(hour)}–${hourLabel((hour + 1) % 24)} today` : 'Select today to see the current hour',
    peak: peak === undefined ? 'No arrivals' : `${hourLabel(peak)}–${hourLabel((peak + 1) % 24)}`,
    peakDetail: `${data.peak_count} arrivals${data.peak_hours.length > 1 ? ` · ${data.peak_hours.length} hours tied` : ''}`,
  };
}
