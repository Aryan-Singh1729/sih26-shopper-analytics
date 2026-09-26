from __future__ import annotations

import base64
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from PIL import Image

from .types import Detection


class DetectorError(RuntimeError):
    pass


class Detector(ABC):
    @property
    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def infer(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError

    def close(self) -> None:
        return None

    def infer_jpeg(self, jpeg: bytes, width: int, height: int) -> list[Detection]:
        with Image.open(io.BytesIO(jpeg)) as picture:
            frame = np.asarray(picture.convert("RGB"), dtype=np.uint8)[:, :, ::-1].copy()
        return self.infer(frame)


class RoboflowInferenceDetector(Detector):
    """Adapter for a self-hosted Roboflow Inference HTTP server.

    The server and this client obtain credentials from ROBOFLOW_API_KEY. The
    value is never stored in configuration, status output, or logs.
    """

    def __init__(self, settings: dict[str, Any]):
        self.api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
        if not self.api_key:
            raise DetectorError("ROBOFLOW_API_KEY is not set")
        self.base_url = str(settings.get("base_url", "http://127.0.0.1:9001")).rstrip("/")
        self.model_id = str(settings.get("model_id", "person-detection-euioa/1")).strip("/")
        if self.model_id != "person-detection-euioa/1":
            raise DetectorError("the configured model must be exactly person-detection-euioa/1")
        self.expected_class = str(settings.get("expected_class", "person"))
        if self.expected_class != "person":
            raise DetectorError("the configured class must be person")
        self.confidence = float(settings.get("confidence", 0.35))
        self.timeout = float(settings.get("request_timeout_seconds", 30))
        self.jpeg_quality = int(settings.get("jpeg_quality", 85))
        self._last_image_size: tuple[int, int] | None = None

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "backend": "self-hosted Roboflow Inference",
            "base_url": self.base_url,
            "model_id": self.model_id,
            "expected_class": self.expected_class,
            "credential_source": "ROBOFLOW_API_KEY",
            "last_image_size": self._last_image_size,
        }

    def infer(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        rgb = frame[:, :, ::-1]
        encoded = io.BytesIO()
        Image.fromarray(rgb).save(encoded, format="JPEG", quality=self.jpeg_quality)
        return self.infer_jpeg(encoded.getvalue(), width, height)

    def infer_jpeg(self, jpeg: bytes, width: int, height: int) -> list[Detection]:
        self._last_image_size = (width, height)
        body = base64.b64encode(jpeg)
        query = urllib.parse.urlencode({"api_key": self.api_key, "confidence": self.confidence})
        url = f"{self.base_url}/{self.model_id}?{query}"
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read(512).decode("utf-8", "replace")
            raise DetectorError(f"Roboflow Inference returned HTTP {error.code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise DetectorError(f"Roboflow Inference is unavailable at {self.base_url}") from error
        return self._parse_predictions(payload, width, height, self.expected_class)

    @staticmethod
    def _parse_predictions(payload: dict[str, Any], width: int, height: int, expected_class: str = "person") -> list[Detection]:
        predictions = payload.get("predictions")
        if not isinstance(predictions, list):
            raise DetectorError("Roboflow response does not contain a predictions list")
        detections: list[Detection] = []
        seen_classes: set[str] = set()
        for prediction in predictions:
            class_name = str(prediction.get("class", ""))
            seen_classes.add(class_name)
            if class_name != expected_class:
                continue
            x = float(prediction["x"])
            y = float(prediction["y"])
            box_width = float(prediction["width"])
            box_height = float(prediction["height"])
            confidence = float(prediction["confidence"])
            x1 = max(0.0, min(width - 1.0, x - box_width / 2.0))
            y1 = max(0.0, min(height - 1.0, y - box_height / 2.0))
            x2 = max(0.0, min(width - 1.0, x + box_width / 2.0))
            y2 = max(0.0, min(height - 1.0, y + box_height / 2.0))
            if x2 > x1 and y2 > y1:
                detections.append(Detection((x1, y1, x2, y2), confidence, 0))
        if predictions and expected_class not in seen_classes:
            raise DetectorError(f"unexpected model classes: {sorted(seen_classes)}")
        return detections


def create_detector(settings: dict[str, Any]) -> Detector:
    backend = str(settings.get("backend", "roboflow_http"))
    if backend == "pc_onnx":
        from .yolox_detector import PcPersonDetector
        return PcPersonDetector(settings)
    if backend == "yolox_local":
        from .yolox_detector import YoloxPersonDetector
        return YoloxPersonDetector(settings)
    if backend == "roboflow_http":
        return RoboflowInferenceDetector(settings)
    raise DetectorError(f"unsupported detector backend: {backend}")
