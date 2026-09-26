from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .types import CrossingEvent, Detection, Direction
from .timezones import resolve_timezone


class PresenceCounter:
    """Count one arrival when a complete person first appears in a clear view."""

    def __init__(self, settings: dict[str, Any], timezone_name: str):
        self.camera_id = f"{settings['camera_id']}:presence-person-v1"
        self.timezone = resolve_timezone(timezone_name)
        self.clear_observations = int(settings.get("clear_observations", 4))
        self.clear_seconds = float(settings.get("clear_seconds", 7))
        self.clear_scene_drop = float(settings.get("clear_scene_drop", 0.05))
        self.present = False
        self.empty_samples = 0
        self.first_empty_at: float | None = None
        self.peak_scene_score: float | None = None

    def update(
        self,
        detections: list[Detection],
        timestamp: float,
        scene_occupied: bool = True,
        scene_score: float | None = None,
    ) -> list[CrossingEvent]:
        if scene_occupied and detections:
            self.empty_samples = 0
            self.first_empty_at = None
            if scene_score is not None:
                self.peak_scene_score = max(self.peak_scene_score or scene_score, scene_score)
            if self.present:
                return []
            self.present = True
            moment = datetime.fromtimestamp(timestamp, timezone.utc)
            return [CrossingEvent(
                event_id=str(uuid.uuid4()),
                timestamp_utc=moment.isoformat(),
                local_date=moment.astimezone(self.timezone).date().isoformat(),
                camera_id=self.camera_id,
                direction=Direction.ENTRY,
                confidence=max(d.confidence for d in detections),
            )]
        relatively_clear = (
            self.present
            and scene_score is not None
            and self.peak_scene_score is not None
            and scene_score <= self.peak_scene_score - self.clear_scene_drop
        )
        if scene_occupied and not relatively_clear:
            self.empty_samples = 0
            self.first_empty_at = None
            return []
        self.empty_samples += 1
        if self.first_empty_at is None:
            self.first_empty_at = timestamp
        if self.empty_samples >= self.clear_observations and timestamp - self.first_empty_at >= self.clear_seconds:
            self.present = False
            self.peak_scene_score = None
        return []
