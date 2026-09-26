from __future__ import annotations

from retail_counter.counter import DoorwayCounter, Side
from retail_counter.types import Direction, TrackView


SETTINGS = {
    "camera_id": "test-door",
    "outside_line": [[0.1, 0.4], [0.9, 0.4]],
    "inside_line": [[0.1, 0.6], [0.9, 0.6]],
    "corridor_polygon": [[0.05, 0.1], [0.95, 0.1], [0.95, 0.9], [0.05, 0.9]],
    "stable_observations": 2,
    "maximum_crossing_seconds": 5,
    "minimum_progress": 0.05,
    "enable_entries": True,
    "enable_exits": True,
}


def track(track_id: int, y: float, confidence: float = 0.9) -> TrackView:
    return TrackView(track_id, (45, y - 5, 55, y + 5), confidence, True, 1.0)


def feed(counter: DoorwayCounter, track_id: int, ys: list[float], start: float = 1000):
    events = []
    for index, y in enumerate(ys):
        events.extend(counter.update([track(track_id, y)], start + index * 0.2))
    return events


def test_classifies_doorway_regions():
    counter = DoorwayCounter(SETTINGS, "Asia/Calcutta", 100, 100)
    assert counter.classify((50, 30)) is Side.OUTSIDE
    assert counter.classify((50, 50)) is Side.TRANSITION
    assert counter.classify((50, 70)) is Side.INSIDE


def test_one_entry_emitted_once_while_person_remains_inside():
    counter = DoorwayCounter(SETTINGS, "Asia/Calcutta", 100, 100)
    events = feed(counter, 1, [30, 30, 45, 50, 70, 70, 72, 71, 70])
    assert [event.direction for event in events] == [Direction.ENTRY]


def test_turnaround_is_not_counted():
    counter = DoorwayCounter(SETTINGS, "Asia/Calcutta", 100, 100)
    events = feed(counter, 1, [30, 30, 45, 52, 45, 30, 30])
    assert events == []


def test_entry_then_exit_are_distinct_events():
    counter = DoorwayCounter(SETTINGS, "Asia/Calcutta", 100, 100)
    events = feed(counter, 1, [30, 30, 45, 70, 70, 50, 30, 30])
    assert [event.direction for event in events] == [Direction.ENTRY, Direction.EXIT]


def test_track_first_seen_inside_does_not_create_entry():
    counter = DoorwayCounter(SETTINGS, "Asia/Calcutta", 100, 100)
    events = feed(counter, 1, [70, 70, 72, 70])
    assert events == []

