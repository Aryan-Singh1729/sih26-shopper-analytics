"""Reset only today's active entrance events, with a recoverable SQLite backup."""
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

root = Path('/home/arduino/retail-entrance-counter/data')
with urllib.request.urlopen('http://127.0.0.1:8080/api/footfall', timeout=5) as response:
    history = json.load(response)
day, camera = history['date'], history['camera_id']
if camera != 'entrance-fixed-2:presence-person-v1':
    raise SystemExit('Unexpected active counter; refusing reset')
database = root / 'events.sqlite3'
if not database.is_file() or database.is_symlink():
    raise SystemExit('Expected regular database missing')
backup = root / ('events-before-reset-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
with sqlite3.connect(database, timeout=10) as connection:
    with sqlite3.connect(backup) as saved:
        connection.backup(saved)
    cursor = connection.execute('DELETE FROM crossing_events WHERE local_date=? AND camera_id=?', (day, camera))
    connection.commit()
    print(json.dumps({'reset_date': day, 'removed_events': cursor.rowcount, 'backup': str(backup)}))
