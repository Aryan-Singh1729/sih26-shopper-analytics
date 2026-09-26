from __future__ import annotations

import io
import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class CapturedFrame:
    sequence: int
    captured_at: float
    jpeg: bytes

    @property
    def image(self) -> np.ndarray:
        with Image.open(io.BytesIO(self.jpeg)) as picture:
            return np.asarray(picture.convert("RGB"), dtype=np.uint8)[:, :, ::-1].copy()


def publish_live_frame(jpeg_path: Path, metadata_path: Path, jpeg: bytes, sequence: int, captured_at: float) -> None:
    jpeg_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".jpg", dir=jpeg_path.parent, delete=False) as handle:
        handle.write(jpeg)
        temporary_jpeg = Path(handle.name)
    os.replace(temporary_jpeg, jpeg_path)
    details = {
        "sequence": sequence,
        "captured_at": captured_at,
        "jpeg_mtime_ns": jpeg_path.stat().st_mtime_ns,
        "jpeg_sha256": hashlib.sha256(jpeg).hexdigest(),
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=metadata_path.parent, delete=False) as handle:
        json.dump(details, handle)
        temporary_metadata = Path(handle.name)
    os.replace(temporary_metadata, metadata_path)


def extract_jpegs(buffer: bytearray) -> list[bytes]:
    frames: list[bytes] = []
    while True:
        start = buffer.find(b"\xff\xd8")
        if start < 0:
            trailing_ff = buffer.endswith(b"\xff")
            buffer.clear()
            if trailing_ff:
                buffer.append(0xff)
            break
        if start:
            del buffer[:start]
        end = buffer.find(b"\xff\xd9", 2)
        if end < 0:
            if len(buffer) > 8_000_000:
                buffer.clear()
            break
        frames.append(bytes(buffer[:end + 2]))
        del buffer[:end + 2]
    return frames


class LatestFrameCamera:
    def __init__(self, settings: dict[str, Any], live_path: Path | None = None, scene_monitor: Any | None = None):
        self.source = str(settings.get("source", "/dev/video0"))
        self.width = int(settings.get("width", 1280))
        self.height = int(settings.get("height", 720))
        self.fps = int(settings.get("fps", 30))
        self.input_format = str(settings.get("fourcc", "MJPG")).lower().replace("mjpg", "mjpeg")
        self.live_path = live_path
        self.live_width = int(settings.get('live_width', self.width))
        self.live_quality = int(settings.get('live_quality', 70))
        self.live_metadata_path = live_path.with_name("retail-edge-live-meta.json") if live_path else None
        self.scene_monitor = scene_monitor
        self.live_interval = 1 / max(1.0, float(settings.get("live_fps", 5)))
        if self.live_path:
            self.live_path.unlink(missing_ok=True)
            self.live_metadata_path.unlink(missing_ok=True)
        self.process: subprocess.Popen | None = None
        self._condition = threading.Condition()
        self._latest: tuple[int, float, bytes] | None = None
        self._candidate: tuple[int, float, bytes] | None = None
        self.candidate_captures = 0
        self.candidate_processed = 0
        self._stopped = False
        self._thread = threading.Thread(target=self._capture_loop, name="camera-capture", daemon=True)
        self._thread.start()

    def _start_process(self) -> subprocess.Popen:
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "v4l2", "-input_format", self.input_format,
            "-framerate", str(self.fps), "-video_size", f"{self.width}x{self.height}",
            "-i", self.source, "-an", "-c:v", "copy", "-f", "mjpeg", "pipe:1",
        ]
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)

    def _publish_live(self, jpeg: bytes, sequence: int, captured_at: float) -> None:
        if self.live_path is None:
            return
        if self.live_width < self.width:
            with Image.open(io.BytesIO(jpeg)) as image:
                target = (self.live_width, round(image.height*self.live_width/image.width))
                image.draft('RGB', target)
                image = image.convert('RGB').resize(target)
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG', quality=self.live_quality)
                jpeg = buffer.getvalue()
        publish_live_frame(self.live_path, self.live_metadata_path, jpeg, sequence, captured_at)

    def _capture_loop(self) -> None:
        sequence = 0
        next_live = 0.0
        while not self._stopped:
            self.process = self._start_process()
            assert self.process.stdout is not None
            buffer = bytearray()
            while not self._stopped:
                chunk = self.process.stdout.read(65536)
                if not chunk:
                    break
                buffer.extend(chunk)
                for jpeg in extract_jpegs(buffer):
                    sequence += 1
                    captured_at = time.time()
                    with self._condition:
                        self._latest = (sequence, captured_at, jpeg)
                        self._condition.notify_all()
                    if time.monotonic() >= next_live:
                        self._publish_live(jpeg, sequence, captured_at)
                        if self.scene_monitor is not None:
                            occupied, _ = self.scene_monitor.occupied(jpeg)
                            if occupied:
                                with self._condition:
                                    self._candidate = (sequence, captured_at, jpeg)
                                    self.candidate_captures += 1
                        next_live = time.monotonic() + self.live_interval
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            if not self._stopped:
                time.sleep(0.5)

    def read_after(self, sequence: int, timeout: float = 2.0) -> CapturedFrame | None:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._stopped and (self._latest is None or self._latest[0] <= sequence):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # USB resets can leave ffmpeg alive but blocked forever.
                    stale = self._latest is None or time.time() - self._latest[1] > 5
                    if stale and self.process is not None and self.process.poll() is None:
                        self.process.terminate()
                    return None
                self._condition.wait(remaining)
            if self._latest is None:
                return None
            if self._candidate is not None and self._candidate[0] <= sequence:
                self._candidate = None
            if self._candidate is not None:
                latest_sequence, captured_at, jpeg = self._candidate
                self._candidate = None
                self.candidate_processed += 1
            else:
                latest_sequence, captured_at, jpeg = self._latest
        return CapturedFrame(latest_sequence, captured_at, jpeg)

    def close(self) -> None:
        self._stopped = True
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        with self._condition:
            self._condition.notify_all()
        self._thread.join(timeout=2)
