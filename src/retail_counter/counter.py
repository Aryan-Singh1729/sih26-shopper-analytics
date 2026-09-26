from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .types import CrossingEvent, Direction, TrackView
from .timezones import resolve_timezone


class Side(str, Enum):
    OUTSIDE = "OUTSIDE"
    TRANSITION = "TRANSITION"
    INSIDE = "INSIDE"
    OUT_OF_CORRIDOR = "OUT_OF_CORRIDOR"


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


@dataclass
class _CrossingState:
    pending_side: Side | None = None
    pending_count: int = 0
    stable_side: Side | None = None
    armed_entry: bool = False
    armed_exit: bool = False
    crossing_started: float | None = None
    starting_progress: float | None = None
    last_seen: float = 0.0


class DoorwayCounter:
    def __init__(self, settings: dict[str, Any], timezone_name: str, frame_width: int, frame_height: int):
        self.camera_id = str(settings["camera_id"])
        self.stable_observations = int(settings.get("stable_observations", 2))
        self.maximum_crossing_seconds = float(settings.get("maximum_crossing_seconds", 5.0))
        self.minimum_progress = float(settings.get("minimum_progress", 0.08))
        self.enable_entries = bool(settings.get("enable_entries", True))
        self.enable_exits = bool(settings.get("enable_exits", False))
        self.timezone = resolve_timezone(timezone_name)
        self.width = frame_width
        self.height = frame_height
        self.outside_line = self._pixels(settings["outside_line"])
        self.inside_line = self._pixels(settings["inside_line"])
        self.corridor = self._pixels(settings["corridor_polygon"])
        outside_mid = self._midpoint(self.outside_line)
        inside_mid = self._midpoint(self.inside_line)
        vector = (inside_mid[0] - outside_mid[0], inside_mid[1] - outside_mid[1])
        length = math.hypot(*vector)
        if length < 2:
            raise ValueError("outside and inside lines are too close")
        self.origin = outside_mid
        self.direction = (vector[0] / length, vector[1] / length)
        self.transition_length = length
        self._states: dict[int, _CrossingState] = {}

    def _pixels(self, points: list[list[float]]) -> list[tuple[float, float]]:
        return [(float(x) * self.width, float(y) * self.height) for x, y in points]

    @staticmethod
    def _midpoint(line: list[tuple[float, float]]) -> tuple[float, float]:
        return ((line[0][0] + line[1][0]) / 2, (line[0][1] + line[1][1]) / 2)

    def progress(self, point: tuple[float, float]) -> float:
        dx, dy = point[0] - self.origin[0], point[1] - self.origin[1]
        return (dx * self.direction[0] + dy * self.direction[1]) / self.transition_length

    def classify(self, point: tuple[float, float]) -> Side:
        if not _point_in_polygon(point, self.corridor):
            return Side.OUT_OF_CORRIDOR
        progress = self.progress(point)
        if progress <= 0:
            return Side.OUTSIDE
        if progress >= 1:
            return Side.INSIDE
        return Side.TRANSITION

    def update(self, tracks: list[TrackView], timestamp: float) -> list[CrossingEvent]:
        events: list[CrossingEvent] = []
        active_ids: set[int] = set()
        for track in tracks:
            if not track.confirmed:
                continue
            active_ids.add(track.track_id)
            state = self._states.setdefault(track.track_id, _CrossingState())
            state.last_seen = timestamp
            point = track.centroid
            side = self.classify(point)
            if side is Side.OUT_OF_CORRIDOR:
                continue
            if side == state.pending_side:
                state.pending_count += 1
            else:
                state.pending_side = side
                state.pending_count = 1
            if side is Side.TRANSITION:
                if state.crossing_started is None:
                    state.crossing_started = timestamp
                    state.starting_progress = self.progress(point)
                continue
            if state.pending_count < self.stable_observations:
                continue
            previous = state.stable_side
            state.stable_side = side
            if side is Side.OUTSIDE:
                state.armed_entry = True
                if previous is Side.INSIDE:
                    event = self._maybe_event(state, track, timestamp, Direction.EXIT, point)
                    if event:
                        events.append(event)
                        state.armed_entry = True
                        state.armed_exit = False
                if previous is not Side.TRANSITION:
                    state.crossing_started = None
                    state.starting_progress = None
            elif side is Side.INSIDE:
                state.armed_exit = True
                if previous is Side.OUTSIDE:
                    event = self._maybe_event(state, track, timestamp, Direction.ENTRY, point)
                    if event:
                        events.append(event)
                        state.armed_entry = False
                        state.armed_exit = True
                if previous is not Side.TRANSITION:
                    state.crossing_started = None
                    state.starting_progress = None
        expiry = max(10.0, self.maximum_crossing_seconds * 2)
        self._states = {track_id: state for track_id, state in self._states.items() if timestamp - state.last_seen <= expiry}
        return events

    def _maybe_event(
        self,
        state: _CrossingState,
        track: TrackView,
        timestamp: float,
        direction: Direction,
        point: tuple[float, float],
    ) -> CrossingEvent | None:
        enabled = self.enable_entries if direction is Direction.ENTRY else self.enable_exits
        armed = state.armed_entry if direction is Direction.ENTRY else state.armed_exit
        if not enabled or not armed or state.crossing_started is None:
            return None
        if timestamp - state.crossing_started > self.maximum_crossing_seconds:
            return None
        progress = self.progress(point)
        start = state.starting_progress if state.starting_progress is not None else progress
        signed_progress = progress - start if direction is Direction.ENTRY else start - progress
        if signed_progress < self.minimum_progress:
            return None
        moment = datetime.fromtimestamp(timestamp, timezone.utc)
        return CrossingEvent(
            event_id=str(uuid.uuid4()),
            timestamp_utc=moment.isoformat(),
            local_date=moment.astimezone(self.timezone).date().isoformat(),
            camera_id=self.camera_id,
            direction=direction,
            confidence=track.confidence,
        )
