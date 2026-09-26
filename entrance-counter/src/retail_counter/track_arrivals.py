"""One saved arrival per anonymous person track, including groups."""
import uuid
from datetime import datetime, timezone
from .types import CrossingEvent, Direction
from .timezones import resolve_timezone


class TrackArrivalCounter:
    def __init__(self, settings, timezone_name):
        self.camera_id = settings['camera_id'] + ':presence-person-v1'
        self.zone = resolve_timezone(timezone_name)
        self.counted = set()
        self.present = False
        self.first_empty = None
        self.clear_seconds = float(settings.get('clear_seconds', 3))
        self.peak_scene = None
        self.clear_drop = float(settings.get('clear_scene_drop', .05))

    def update(self, tracks, timestamp, scene_occupied=True, scene_score=None):
        visible = [track for track in tracks if track.confirmed]
        if visible:
            self.first_empty = None
            self.present = True
            if scene_score is not None:
                self.peak_scene = max(self.peak_scene or scene_score, scene_score)
            events = []
            for track in visible:
                if track.track_id in self.counted:
                    continue
                self.counted.add(track.track_id)
                moment = datetime.fromtimestamp(timestamp, timezone.utc)
                events.append(CrossingEvent(str(uuid.uuid4()), moment.isoformat(),
                                           moment.astimezone(self.zone).date().isoformat(),
                                           self.camera_id, Direction.ENTRY, track.confidence))
            return events
        relatively_clear = scene_score is not None and self.peak_scene is not None and scene_score <= self.peak_scene-self.clear_drop
        if not scene_occupied or relatively_clear:
            if self.first_empty is None:
                self.first_empty = timestamp
            if timestamp-self.first_empty >= self.clear_seconds:
                self.counted.clear()
                self.present = False
                self.peak_scene = None
        else:
            self.first_empty = None
        return []
