"""One-time, exact-inventory purge after verified person-model cutover."""

import sqlite3
from pathlib import Path

from retail_counter.purge_legacy import purge_inspected_legacy_events


DB = Path("/home/arduino/retail-entrance-counter/data/events.sqlite3")
EXPECTED_LEGACY = {
    "entrance-1": 3,
    "entrance-1:presence-v2": 1,
    "entrance-1:presence-v3": 5,
    "entrance-1:presence-v4": 5,
    "entrance-fixed-2:presence-v4": 36,
}
EXPECTED_NEW = 4


def main() -> None:
    if not DB.is_file() or DB.is_symlink():
        raise SystemExit("refusing: expected regular event database not found")
    with sqlite3.connect(DB, timeout=10) as connection:
        deleted = purge_inspected_legacy_events(connection, EXPECTED_LEGACY, EXPECTED_NEW)
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("VACUUM")
        print(f"deleted={deleted}; preserved_new={EXPECTED_NEW}")


if __name__ == "__main__":
    main()
