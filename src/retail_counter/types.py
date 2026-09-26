from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class Detection:
    xyxy: tuple[float, float, float, float]
    confidence: float
    class_id: int = 0

    @property
    def centroid(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def as_array(self) -> np.ndarray:
        return np.asarray(self.xyxy, dtype=np.float32)


@dataclass(frozen=True)
class TrackView:
    track_id: int
    xyxy: tuple[float, float, float, float]
    confidence: float
    confirmed: bool
    age_seconds: float
    lost_seconds: float = 0.0

    @property
    def centroid(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class Direction(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


@dataclass(frozen=True)
class CrossingEvent:
    event_id: str
    timestamp_utc: str
    local_date: str
    camera_id: str
    direction: Direction
    confidence: float


@dataclass(frozen=True)
class CounterSnapshot:
    entries_today: int
    exits_today: int
    current_occupancy: int
    local_date: str


@dataclass
class PerformanceSnapshot:
    capture_fps: float = 0.0
    processed_fps: float = 0.0
    inference_ms_p50: float = 0.0
    inference_ms_p95: float = 0.0
    end_to_end_ms_p95: float = 0.0
    dropped_frames: int = 0
    visible_tracks: int = 0
    rss_mb: float = 0.0
    available_memory_mb: float = 0.0
    cpu_percent: float = 0.0
    temperature_c: float | None = None
    samples: Sequence[float] = field(default_factory=tuple, repr=False)

