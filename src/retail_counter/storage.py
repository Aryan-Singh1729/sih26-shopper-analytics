from __future__ import annotations

import sqlite3
from pathlib import Path

from .types import CounterSnapshot, CrossingEvent, Direction


class EventStore:
    def __init__(self, path: str, initial_occupancy: int = 0):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initial_occupancy = max(0, int(initial_occupancy))
        self.connection = sqlite3.connect(self.path, timeout=10)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crossing_events (
                event_id TEXT PRIMARY KEY,
                timestamp_utc TEXT NOT NULL,
                local_date TEXT NOT NULL,
                camera_id TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('ENTRY', 'EXIT')),
                confidence REAL NOT NULL
            )
            """
        )
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_crossing_local_date ON crossing_events(local_date)")
        self.connection.commit()

    def add(self, event: CrossingEvent) -> bool:
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO crossing_events VALUES (?, ?, ?, ?, ?, ?)",
            (event.event_id, event.timestamp_utc, event.local_date, event.camera_id, event.direction.value, event.confidence),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def snapshot(self, local_date: str, camera_id: str | None = None) -> CounterSnapshot:
        if camera_id is None:
            rows = dict(self.connection.execute(
                "SELECT direction, COUNT(*) FROM crossing_events WHERE local_date = ? GROUP BY direction", (local_date,)
            ).fetchall())
        else:
            rows = dict(self.connection.execute(
                "SELECT direction, COUNT(*) FROM crossing_events WHERE local_date = ? AND camera_id = ? GROUP BY direction",
                (local_date, camera_id),
            ).fetchall())
        entries = int(rows.get(Direction.ENTRY.value, 0))
        exits = int(rows.get(Direction.EXIT.value, 0))
        return CounterSnapshot(entries, exits, max(0, self.initial_occupancy + entries - exits), local_date)

    def close(self) -> None:
        self.connection.close()
