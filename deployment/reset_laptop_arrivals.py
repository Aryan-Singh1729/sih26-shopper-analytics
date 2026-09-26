"""Reset the current dashboard date, retaining a recoverable SQLite backup."""
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1]/'data'
with urllib.request.urlopen('http://127.0.0.1:8081/api/footfall',timeout=5) as response:
    history=json.load(response)
day=history['date']
database=root/'laptop-visual-arrivals.sqlite3'
if not database.is_file() or database.is_symlink():
    raise SystemExit('Expected regular arrival database missing')
backup=root/('arrivals-before-reset-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.sqlite3')
with sqlite3.connect(database,timeout=10) as connection:
    with sqlite3.connect(backup) as saved:connection.backup(saved)
    cursor=connection.execute('DELETE FROM visual_arrivals WHERE local_date=?',(day,))
    connection.commit()
    print(json.dumps({'date':day,'removed_events':cursor.rowcount,'backup':str(backup)}))
