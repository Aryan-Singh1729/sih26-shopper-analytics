from datetime import datetime, timezone

from retail_counter.storage import EventStore
from retail_counter.types import CrossingEvent, Direction


def event(event_id: str, direction: Direction) -> CrossingEvent:
    return CrossingEvent(event_id, datetime.now(timezone.utc).isoformat(), "2026-09-25", "door", direction, 0.9)


def test_store_is_idempotent_and_computes_counts(tmp_path):
    store = EventStore(str(tmp_path / "events.sqlite3"), initial_occupancy=2)
    assert store.add(event("one", Direction.ENTRY))
    assert not store.add(event("one", Direction.ENTRY))
    assert store.add(event("two", Direction.EXIT))
    snapshot = store.snapshot("2026-09-25")
    assert snapshot.entries_today == 1
    assert snapshot.exits_today == 1
    assert snapshot.current_occupancy == 2
    store.close()
