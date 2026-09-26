from __future__ import annotations

import json
import logging
import os
import signal
import tempfile
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .camera import LatestFrameCamera
from .config import AppConfig
from .detector import create_detector
from .metrics import Metrics
from .presence import PresenceCounter
from .track_arrivals import TrackArrivalCounter
from .preview import write_detection_preview
from .scene import SceneMonitor
from .storage import EventStore
from .tracker import ByteTracker
from .timezones import resolve_timezone
from .types import Detection


LOGGER = logging.getLogger("retail_counter")


def person_boxes_payload(detections: list[Detection]) -> list[dict]:
    return [
        {"class": "person", "xyxy": list(detection.xyxy), "confidence": detection.confidence}
        for detection in detections
    ]


def filter_person_detections(
    raw_detections: list[Detection],
    jpeg: bytes,
    frame_width: int,
    frame_height: int,
    detection_roi: tuple[float, float, float, float],
    scene: SceneMonitor,
    edge_margin: float,
) -> list[Detection]:
    x1, y1, x2, y2 = detection_roi
    return [
        detection for detection in raw_detections
        if x1 <= detection.centroid[0] / frame_width <= x2
        and y1 <= detection.centroid[1] / frame_height <= y2
        and detection.xyxy[0] / frame_width >= edge_margin
        and detection.xyxy[1] / frame_height >= edge_margin
        and detection.xyxy[2] / frame_width <= 1 - edge_margin
        and detection.xyxy[3] / frame_height <= 1 - edge_margin
        and scene.box_changed_fraction(
            jpeg, detection.xyxy, (frame_width, frame_height)
        ) >= 0.08
    ]


class EntranceCounterApp:
    def __init__(self, config: AppConfig):
        self.config = config
        self.running = True
        self.detector = create_detector(config.model)
        self.tracker = ByteTracker(config.tracking)
        self.scene = SceneMonitor(
            Path(config.runtime["empty_scene_file"]),
            float(config.runtime.get("scene_threshold", 0.025)),
        )
        self.camera = LatestFrameCamera(
            config.camera,
            Path(config.runtime.get("live_file", "/dev/shm/retail-edge-live.jpg")),
            None if config.model.get("backend") == "pc_onnx" else self.scene,
        )
        self.frame_width = int(config.camera.get("width", 1280))
        self.frame_height = int(config.camera.get("height", 720))
        self.detection_roi = tuple(float(value) for value in config.camera.get("detection_roi", [0, 0, 1, 1]))
        self.full_person_edge_margin = float(config.camera.get("full_person_edge_margin", 0.02))
        self.per_person_arrivals = config.doorway.get('counting_mode') == 'per_person_tracks'
        counter_class = TrackArrivalCounter if self.per_person_arrivals else PresenceCounter
        self.counter = counter_class(config.doorway, config.storage["timezone"])
        self.store = EventStore(config.storage["database"], config.storage.get("initial_occupancy", 0))
        self.metrics = Metrics()
        self.timezone = resolve_timezone(config.storage["timezone"])
        self.started_at = time.time()
        self.warmup = float(config.runtime.get("startup_warmup_seconds", 2.0))
        self.metrics_interval = float(config.runtime.get("metrics_interval_seconds", 5.0))
        self.status_path = Path(config.runtime["status_file"])
        self.detection_path = Path(config.runtime.get("detection_file", "/dev/shm/retail-edge-detection.jpg"))
        self.detected_persons = 0
        self.scene_occupied = False
        self.scene_score = 0.0
        self.ignored_detections = 0
        self.detection_confidence = None
        self.last_detection_at = None
        self.result_at = None
        self.person_boxes: list[dict] = []
        self.frame_sequence = 0
        self.raw_persons = 0
        self.raw_confidence = None
        self.frame_boxes = []
        self.captured_at = 0.0

    def run(self) -> None:
        LOGGER.info("model metadata: %s", json.dumps(self.detector.metadata, default=str))
        last_sequence = 0
        next_status = time.monotonic()
        while self.running:
            frame = self.camera.read_after(last_sequence)
            if frame is None:
                LOGGER.warning("camera frame timeout")
                continue
            last_sequence = frame.sequence
            self.frame_sequence = frame.sequence
            self.captured_at = frame.captured_at
            started = time.perf_counter()
            raw_detections = self.detector.infer_jpeg(frame.jpeg, self.frame_width, self.frame_height)
            self.raw_persons = len(raw_detections)
            self.raw_confidence = max((d.confidence for d in raw_detections), default=None)
            self.frame_boxes = person_boxes_payload(raw_detections)
            detections = filter_person_detections(
                raw_detections, frame.jpeg, self.frame_width,
                self.frame_height, self.detection_roi, self.scene,
                self.full_person_edge_margin,
            )
            self.ignored_detections = len(raw_detections) - len(detections)
            inference_ms = (time.perf_counter() - started) * 1000
            tracks = self.tracker.update(detections, frame.captured_at)
            self.scene_occupied, self.scene_score = self.scene.occupied(frame.jpeg)
            events = self.counter.update(tracks if self.per_person_arrivals else detections,
                                         frame.captured_at, self.scene_occupied, self.scene_score)
            if self.config.doorway.get('counting_mode') == 'external_visual':
                events = []
            self.detected_persons = len(detections)
            self.detection_confidence = max((d.confidence for d in detections), default=None)
            self.person_boxes = person_boxes_payload(detections)
            self.result_at = datetime.now().astimezone().isoformat()
            write_detection_preview(frame.jpeg, detections, self.detection_path)
            if detections:
                self.last_detection_at = datetime.now().astimezone().isoformat()
            if time.time() - self.started_at >= self.warmup:
                for event in events:
                    if self.store.add(event):
                        LOGGER.info("crossing %s confidence=%.3f", event.direction.value, event.confidence)
            now = time.time()
            self.metrics.record(frame.sequence, now, inference_ms, frame.captured_at)
            if events or time.monotonic() >= next_status:
                self._write_status(tracks)
                next_status = time.monotonic() + self.metrics_interval

    def _write_status(self, tracks) -> None:
        local_date = datetime.now(self.timezone).date().isoformat()
        snapshot = self.store.snapshot(local_date, self.counter.camera_id)
        performance = self.metrics.snapshot(sum(track.confirmed for track in tracks))
        payload = {
            "healthy": True,
            "updated_at": datetime.now().astimezone().isoformat(),
            "counter": asdict(snapshot),
            "performance": asdict(performance),
            "camera": {
                "candidate_captures": self.camera.candidate_captures,
                "candidate_processed": self.camera.candidate_processed,
            },
            "model": self.detector.metadata,
            "detection": {
                "raw_persons": self.raw_persons,
                "raw_confidence": self.raw_confidence,
                "frame_boxes": self.frame_boxes,
                "persons": self.detected_persons,
                "ignored_outside_area": self.ignored_detections,
                "confidence": self.detection_confidence,
                "boxes": self.person_boxes,
                "image_size": [self.frame_width, self.frame_height],
                "result_at": self.result_at,
                "frame_sequence": self.frame_sequence,
                "captured_at": self.captured_at,
                "last_detected_at": self.last_detection_at,
                "present": self.counter.present,
                "scene_occupied": self.scene_occupied,
                "scene_score": self.scene_score,
            },
        }
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.status_path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, default=str)
            temporary = Path(handle.name)
        os.replace(temporary, self.status_path)
        LOGGER.info(
            "entries=%d exits=%d visible=%d fps=%.2f inference_p95=%.1fms rss=%.1fMB",
            snapshot.entries_today,
            snapshot.exits_today,
            performance.visible_tracks,
            performance.processed_fps,
            performance.inference_ms_p95,
            performance.rss_mb,
        )

    def stop(self, *_args) -> None:
        self.running = False

    def close(self) -> None:
        self.camera.close()
        self.detector.close()
        self.store.close()

    def install_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
