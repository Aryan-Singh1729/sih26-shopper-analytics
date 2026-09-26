"""Read-only, timezone-aware aggregation of saved entrance events."""
import sqlite3
from datetime import date, datetime
from pathlib import Path
from .timezones import resolve_timezone


def hourly_footfall(database, day, camera_id, timezone_name='Asia/Calcutta'):
    date.fromisoformat(day)
    zone = resolve_timezone(timezone_name)
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    try:
        rows = connection.execute(
            'SELECT timestamp_utc FROM crossing_events WHERE local_date=? AND camera_id=? AND direction=? ORDER BY timestamp_utc',
            (day, camera_id, 'ENTRY')).fetchall()
        dates = [row[0] for row in connection.execute(
            'SELECT DISTINCT local_date FROM crossing_events WHERE camera_id=? AND direction=? ORDER BY local_date DESC LIMIT 30',
            (camera_id, 'ENTRY'))]
    finally:
        connection.close()
    counts = [0]*24
    last_arrival = None
    for (timestamp,) in rows:
        moment = datetime.fromisoformat(timestamp).astimezone(zone)
        if moment.date().isoformat() != day:
            continue
        counts[moment.hour] += 1
        last_arrival = moment.isoformat()
    peak = max(counts)
    return {'date': day, 'timezone': timezone_name, 'server_time': datetime.now(zone).isoformat(),
            'total_arrivals': sum(counts), 'hourly': [{'hour': hour, 'arrivals': value} for hour, value in enumerate(counts)],
            'peak_count': peak, 'peak_hours': [hour for hour, value in enumerate(counts) if value == peak] if peak else [],
            'last_arrival': last_arrival, 'available_dates': dates, 'camera_id': camera_id}
