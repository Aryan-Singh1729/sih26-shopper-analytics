"""Local Arduino/Edge Impulse YOLOX-Nano person adapter."""
import io
import json
import math
import urllib.request
import urllib.error
import http.client
import urllib.parse
from PIL import Image
from .detector import Detector, DetectorError
from .types import Detection


class YoloxPersonDetector(Detector):
    def __init__(self, settings):
        self.base_url = str(settings.get("base_url", "http://127.0.0.1:1337")).rstrip("/")
        self.confidence = float(settings.get("confidence", 0.5))
        self.timeout = float(settings.get("request_timeout_seconds", 5))

    @property
    def metadata(self):
        return {"backend": "local Edge Impulse", "model_id": "arduino-yolox-nano-v7",
                "model_type": "YOLOX-Nano", "expected_class": "person", "base_url": self.base_url}

    def infer(self, frame):
        height, width = frame.shape[:2]
        buffer = io.BytesIO()
        Image.fromarray(frame[:, :, ::-1]).save(buffer, format="JPEG")
        return self.infer_jpeg(buffer.getvalue(), width, height)

    def infer_jpeg(self, jpeg, width, height):
        boundary = "retail-edge-yolox"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\n"
                "Content-Type: image/jpeg\r\n\r\n").encode() + jpeg + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(self.base_url + "/api/image", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise DetectorError("local YOLOX runner unavailable or invalid response") from error
        return self.parse_predictions(payload, width, height)

    def parse_predictions(self, payload, width, height):
        try:
            boxes = payload["result"]["bounding_boxes"]
            if not isinstance(boxes, list):
                raise ValueError("boxes must be a list")
            detections = []
            for box in boxes:
                if box["label"] != "person" or float(box["value"]) < self.confidence:
                    continue
                x, y, w, h, score = (float(box[key]) for key in ("x", "y", "width", "height", "value"))
                if not all(math.isfinite(v) for v in (x, y, w, h, score)) or w <= 0 or h <= 0 or not 0 <= score <= 1:
                    raise ValueError("invalid geometry")
                xyxy = (max(0, x), max(0, y), min(width - 1, x + w), min(height - 1, y + h))
                if xyxy[2] > xyxy[0] and xyxy[3] > xyxy[1]:
                    detections.append(Detection(xyxy, score, 0))
            return detections
        except (KeyError, TypeError, ValueError) as error:
            raise DetectorError("invalid YOLOX person output") from error


class PcPersonDetector(YoloxPersonDetector):
    def __init__(self, settings):
        super().__init__(settings)
        self.connection = None
        self.last_server_ms = None
        self.runtime_backend = None

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def infer_jpeg(self, jpeg, width, height):
        with Image.open(io.BytesIO(jpeg)) as image:
            target_width = min(640, width)
            target_height = round(height * target_width / width)
            image.draft('RGB', (target_width, target_height))
            resized = image.convert('RGB').resize((target_width, target_height))
            buffer = io.BytesIO()
            resized.save(buffer, format='JPEG', quality=70)
        if self.connection is None:
            url = urllib.parse.urlsplit(self.base_url)
            self.connection = http.client.HTTPConnection(url.hostname, url.port, timeout=self.timeout)
        try:
            self.connection.request('POST', '/api/image', body=buffer.getvalue(),
                                    headers={'Content-Type': 'image/jpeg'})
            response = self.connection.getresponse()
            payload = json.loads(response.read())
            if response.status != 200:
                raise DetectorError('PC inference request failed')
            self.last_server_ms = payload.get('latency_ms')
            self.runtime_backend = payload.get('backend')
        except (OSError, http.client.HTTPException, ValueError) as error:
            self.close()
            raise DetectorError('PC inference connection failed') from error
        detections = self.parse_predictions(payload, target_width, target_height)
        return [Detection((d.xyxy[0] * width / target_width,
                           d.xyxy[1] * height / target_height,
                           d.xyxy[2] * width / target_width,
                           d.xyxy[3] * height / target_height), d.confidence, d.class_id)
                for d in detections]

    @property
    def metadata(self):
        mediapipe = self.runtime_backend == 'MediaPipe EfficientDet-Lite0'
        return {"backend": "PC MediaPipe EfficientDet-Lite0 (SSH tunnel)" if mediapipe else "PC ONNX Runtime CPU (SSH tunnel)",
                "model_id": "efficientdet-lite0-int8" if mediapipe else "person-detection-euioa/1", "model_type": "MediaPipe Object Detector" if mediapipe else "YOLOv8 ONNX",
                "expected_class": "person", "base_url": self.base_url,
                "server_processing_ms": self.last_server_ms}
