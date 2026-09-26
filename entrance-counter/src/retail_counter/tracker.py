from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .types import Detection, TrackView


def _iou_matrix(track_boxes: np.ndarray, detection_boxes: np.ndarray) -> np.ndarray:
    if len(track_boxes) == 0 or len(detection_boxes) == 0:
        return np.empty((len(track_boxes), len(detection_boxes)), dtype=np.float32)
    left_top = np.maximum(track_boxes[:, None, :2], detection_boxes[None, :, :2])
    right_bottom = np.minimum(track_boxes[:, None, 2:], detection_boxes[None, :, 2:])
    size = np.maximum(0, right_bottom - left_top)
    intersection = size[..., 0] * size[..., 1]
    track_area = np.prod(np.maximum(0, track_boxes[:, 2:] - track_boxes[:, :2]), axis=1)
    detection_area = np.prod(np.maximum(0, detection_boxes[:, 2:] - detection_boxes[:, :2]), axis=1)
    union = track_area[:, None] + detection_area[None, :] - intersection
    return np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)


def _greedy_match(iou: np.ndarray, threshold: float) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    remaining_rows = set(range(iou.shape[0]))
    remaining_cols = set(range(iou.shape[1]))
    matches: list[tuple[int, int]] = []
    while remaining_rows and remaining_cols:
        best = max(((float(iou[r, c]), r, c) for r in remaining_rows for c in remaining_cols), default=(-1, -1, -1))
        score, row, col = best
        if score < threshold:
            break
        matches.append((row, col))
        remaining_rows.remove(row)
        remaining_cols.remove(col)
    return matches, sorted(remaining_rows), sorted(remaining_cols)


def _xyxy_to_xyah(box: np.ndarray) -> np.ndarray:
    width = max(1.0, float(box[2] - box[0]))
    height = max(1.0, float(box[3] - box[1]))
    return np.asarray([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2, width / height, height], dtype=np.float32)


def _xyah_to_xyxy(state: np.ndarray) -> np.ndarray:
    cx, cy, aspect, height = state[:4]
    width = max(1.0, aspect * height)
    height = max(1.0, height)
    return np.asarray([cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2], dtype=np.float32)


class KalmanXYAH:
    def __init__(self, measurement: np.ndarray):
        self.mean = np.r_[measurement, np.zeros(4, dtype=np.float32)]
        self.covariance = np.eye(8, dtype=np.float32) * 10.0

    def predict(self, dt: float) -> None:
        dt = max(0.001, min(dt, 1.0))
        motion = np.eye(8, dtype=np.float32)
        for i in range(4):
            motion[i, i + 4] = dt
        height = max(1.0, float(self.mean[3]))
        process = np.diag([
            (height / 20) ** 2, (height / 20) ** 2, 1e-4, (height / 20) ** 2,
            (height / 160) ** 2, (height / 160) ** 2, 1e-6, (height / 160) ** 2,
        ]).astype(np.float32)
        self.mean = motion @ self.mean
        self.covariance = motion @ self.covariance @ motion.T + process

    def update(self, measurement: np.ndarray) -> None:
        projection = np.eye(4, 8, dtype=np.float32)
        height = max(1.0, float(self.mean[3]))
        noise = np.diag([(height / 10) ** 2, (height / 10) ** 2, 1e-2, (height / 10) ** 2]).astype(np.float32)
        projected_mean = projection @ self.mean
        projected_cov = projection @ self.covariance @ projection.T + noise
        gain = self.covariance @ projection.T @ np.linalg.pinv(projected_cov)
        self.mean = self.mean + gain @ (measurement - projected_mean)
        self.covariance = self.covariance - gain @ projection @ self.covariance


@dataclass
class _Track:
    track_id: int
    filter: KalmanXYAH
    confidence: float
    created_at: float
    last_seen: float
    hits: int = 1
    lost: bool = False

    @property
    def box(self) -> np.ndarray:
        return _xyah_to_xyxy(self.filter.mean)

    def predict(self, timestamp: float) -> None:
        self.filter.predict(timestamp - self.last_seen)

    def update(self, detection: Detection, timestamp: float) -> None:
        self.filter.update(_xyxy_to_xyah(detection.as_array()))
        self.confidence = detection.confidence
        self.last_seen = timestamp
        self.hits += 1
        self.lost = False


class ByteTracker:
    """Small-memory ByteTrack-style tracker using two confidence association passes."""

    def __init__(self, settings: dict[str, Any]):
        self.high_threshold = float(settings.get("high_threshold", 0.5))
        self.low_threshold = float(settings.get("low_threshold", 0.1))
        self.new_track_threshold = float(settings.get("new_track_threshold", 0.55))
        self.match_iou = float(settings.get("match_iou", 0.2))
        self.low_match_iou = float(settings.get("low_match_iou", 0.15))
        self.buffer_seconds = float(settings.get("track_buffer_seconds", 1.5))
        self.minimum_hits = int(settings.get("minimum_hits", 3))
        self._tracks: list[_Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection], timestamp: float) -> list[TrackView]:
        for track in self._tracks:
            track.predict(timestamp)
        high = [d for d in detections if d.confidence >= self.high_threshold]
        low = [d for d in detections if self.low_threshold <= d.confidence < self.high_threshold]
        unmatched_tracks = list(range(len(self._tracks)))

        matched, unmatched_tracks, unmatched_high = self._associate(unmatched_tracks, high, self.match_iou)
        for track_index, detection_index in matched:
            self._tracks[track_index].update(high[detection_index], timestamp)

        matched_low, unmatched_tracks, _ = self._associate(unmatched_tracks, low, self.low_match_iou)
        for track_index, detection_index in matched_low:
            self._tracks[track_index].update(low[detection_index], timestamp)

        for index in unmatched_tracks:
            self._tracks[index].lost = True

        for index in unmatched_high:
            detection = high[index]
            if detection.confidence >= self.new_track_threshold:
                self._tracks.append(_Track(
                    self._next_id,
                    KalmanXYAH(_xyxy_to_xyah(detection.as_array())),
                    detection.confidence,
                    timestamp,
                    timestamp,
                ))
                self._next_id += 1

        self._tracks = [track for track in self._tracks if timestamp - track.last_seen <= self.buffer_seconds]
        return [
            TrackView(
                track_id=track.track_id,
                xyxy=tuple(float(v) for v in track.box),
                confidence=track.confidence,
                confirmed=track.hits >= self.minimum_hits,
                age_seconds=max(0.0, timestamp - track.created_at),
                lost_seconds=max(0.0, timestamp - track.last_seen),
            )
            for track in self._tracks
            if not track.lost
        ]

    def _associate(self, track_indices: list[int], detections: list[Detection], threshold: float):
        track_boxes = np.asarray([self._tracks[i].box for i in track_indices], dtype=np.float32).reshape(-1, 4)
        detection_boxes = np.asarray([d.xyxy for d in detections], dtype=np.float32).reshape(-1, 4)
        matches, unmatched_rows, unmatched_detections = _greedy_match(_iou_matrix(track_boxes, detection_boxes), threshold)
        mapped = [(track_indices[row], col) for row, col in matches]
        return mapped, [track_indices[row] for row in unmatched_rows], unmatched_detections

