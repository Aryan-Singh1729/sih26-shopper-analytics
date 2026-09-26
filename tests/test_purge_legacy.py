from retail_counter.purge_legacy import purge_legacy_events, purge_inspected_legacy_events
from retail_counter.storage import EventStore
from retail_counter.types import CrossingEvent, Direction
import pytest


def test_purge_removes_only_inspected_legacy_camera_ids(tmp_path):
    store = EventStore(str(tmp_path / "events.sqlite3"))
    for event_id, camera_id in [
        ("old-one", "entrance-1:presence-v4"),
        ("old-two", "entrance-fixed-2:presence-v4"),
        ("new-one", "entrance-fixed-2:presence-person-v1"),
        ("other", "unrelated-camera"),
    ]:
        store.add(CrossingEvent(event_id, "2026-09-26T00:00:00+00:00", "2026-09-26", camera_id, Direction.ENTRY, 0.9))

    deleted = purge_legacy_events(store.connection, {"entrance-1:presence-v4", "entrance-fixed-2:presence-v4"})

    assert deleted == 2
    assert store.connection.execute("SELECT event_id FROM crossing_events ORDER BY event_id").fetchall() == [
        ("new-one",), ("other",),
    ]
    store.close()


def test_empty_legacy_id_set_does_not_delete_anything(tmp_path):
    store = EventStore(str(tmp_path / "events.sqlite3"))
    store.add(CrossingEvent("new", "2026-09-26T00:00:00+00:00", "2026-09-26", "entrance-fixed-2:presence-person-v1", Direction.ENTRY, 0.9))
    assert purge_legacy_events(store.connection, set()) == 0
    assert store.connection.execute("SELECT COUNT(*) FROM crossing_events").fetchone()[0] == 1
    store.close()


def test_purge_refuses_new_model_camera_id(tmp_path):
    store = EventStore(str(tmp_path / "events.sqlite3"))
    store.add(CrossingEvent("new", "2026-09-26T00:00:00+00:00", "2026-09-26", "entrance-fixed-2:presence-person-v1", Direction.ENTRY, 0.9))
    with pytest.raises(ValueError, match="new-model"):
        purge_legacy_events(store.connection, {"entrance-fixed-2:presence-person-v1"})
    assert store.connection.execute("SELECT COUNT(*) FROM crossing_events").fetchone()[0] == 1
    store.close()


def test_purge_inspected_events_checks_counts_and_preserves_new_rows(tmp_path):
    store = EventStore(str(tmp_path / "events.sqlite3"))
    for event_id, camera_id in [
        ("old", "entrance-1"),
        ("new", "entrance-fixed-2:presence-person-v1"),
    ]:
        store.add(CrossingEvent(event_id, "2026-09-26T00:00:00+00:00", "2026-09-26", camera_id, Direction.ENTRY, 0.9))
    assert purge_inspected_legacy_events(store.connection, {"entrance-1": 1}, expected_new_count=1) == 1
    assert store.connection.execute("SELECT camera_id FROM crossing_events").fetchall() == [
        ("entrance-fixed-2:presence-person-v1",),
    ]
    store.close()


def test_purge_inspected_events_refuses_changed_inventory(tmp_path):
    store = EventStore(str(tmp_path / "events.sqlite3"))
    store.add(CrossingEvent("old", "2026-09-26T00:00:00+00:00", "2026-09-26", "entrance-1", Direction.ENTRY, 0.9))
    with pytest.raises(ValueError, match="inventory changed"):
        purge_inspected_legacy_events(store.connection, {"entrance-1": 2}, expected_new_count=0)
    assert store.connection.execute("SELECT COUNT(*) FROM crossing_events").fetchone()[0] == 1
    store.close()
