from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
import urllib.parse
import sqlite3
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from .footfall import hourly_footfall
from .timezones import resolve_timezone


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "web"
STATUS_PATH = PROJECT_ROOT / "data" / "status.json"
PREVIEW_PATH = Path("/dev/shm/retail-edge-live.jpg")
LIVE_METADATA_PATH = Path("/dev/shm/retail-edge-live-meta.json")
DETECTION_PATH = Path("/dev/shm/retail-edge-detection.jpg")
VERIFICATION_PATH = PROJECT_ROOT / "deployment" / "unoq-verification.json"


def inference_health() -> tuple[bool, dict[str, Any]]:
    try:
        runtime = read_json(STATUS_PATH)
        model = runtime.get("model", {})
        if model.get("backend", "").startswith("PC "):
            # A successful recent result proves the tunnel and model are working.
            # Do not add a second round-trip to every 200ms browser status poll.
            result_at = runtime.get("detection", {}).get("result_at")
            age = time.time() - datetime.fromisoformat(result_at).timestamp() if result_at else float('inf')
            return bool(runtime.get("healthy")) and 0 <= age < 3, {"name": model.get("backend")}
        base_url = model.get("base_url", "http://127.0.0.1:9001")
        with urllib.request.urlopen(base_url.rstrip("/") + "/", timeout=1.5) as response:
            payload = json.load(response)
            return response.status == 200, payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, TypeError):
        return False, {}


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_live_snapshot(jpeg_path: Path, metadata_path: Path) -> tuple[bytes, dict[str, Any]] | None:
    metadata = read_json(metadata_path)
    try:
        sequence = int(metadata["sequence"])
        captured_at = float(metadata["captured_at"])
        expected_mtime = int(metadata["jpeg_mtime_ns"])
        if time.time() - captured_at > 1.0 or captured_at - time.time() > 0.5:
            return None
        before = jpeg_path.stat().st_mtime_ns
        if before != expected_mtime:
            return None
        jpeg = jpeg_path.read_bytes()
        if jpeg_path.stat().st_mtime_ns != before:
            return None
        if hashlib.sha256(jpeg).hexdigest() != metadata["jpeg_sha256"]:
            return None
    except (KeyError, ValueError, TypeError, OSError):
        return None
    return jpeg, {"sequence": sequence, "captured_at": captured_at, "jpeg_mtime_ns": expected_mtime}


def live_part(jpeg_path: Path, metadata_path: Path, last_sequence: int) -> bytes | None:
    snapshot = read_live_snapshot(jpeg_path, metadata_path)
    if snapshot is None:
        return None
    jpeg, metadata = snapshot
    if metadata["sequence"] <= last_sequence:
        return None
    return (
        b"--frame\r\nContent-Type: image/jpeg\r\n"
        + f"Content-Length: {len(jpeg)}\r\n".encode()
        + f"X-Frame-Sequence: {metadata['sequence']}\r\n".encode()
        + f"X-Captured-At: {metadata['captured_at']}\r\n\r\n".encode()
        + jpeg + b"\r\n"
    )


def build_status() -> dict[str, Any]:
    runtime = read_json(STATUS_PATH)
    verification = read_json(VERIFICATION_PATH)
    inference_ok, inference_payload = inference_health()
    counter = runtime.get("counter", {})
    performance = runtime.get("performance", {})
    model = runtime.get("model", {})
    verified_inference = verification.get("inference", {})
    if not model:
        model = {
            "model_id": verified_inference.get("model_id", "person-detection-euioa/1"),
            "model_type": verified_inference.get("model_type", "Roboflow 3.0 Object Detection (Fast)"),
        }
    try:
        status_age_seconds = max(0.0, datetime.now().timestamp() - STATUS_PATH.stat().st_mtime)
    except OSError:
        status_age_seconds = None
    counter_running = bool(runtime.get("healthy")) and status_age_seconds is not None and status_age_seconds < 15
    try:
        frame_age_seconds = max(0.0, datetime.now().timestamp() - PREVIEW_PATH.stat().st_mtime)
    except OSError:
        frame_age_seconds = None
    return {
        "updated_at": datetime.now().astimezone().isoformat(),
        "counter_running": counter_running,
        "stream_available": frame_age_seconds is not None and frame_age_seconds < 3,
        "frame_age_seconds": frame_age_seconds,
        "counter": counter,
        "performance": performance,
        "camera": runtime.get("camera", {}),
        "model": model,
        "detection": runtime.get("detection", {}),
        "detection_frame_available": DETECTION_PATH.is_file(),
        "inference": {
            "healthy": inference_ok,
            "name": inference_payload.get("name"),
            "version": inference_payload.get("version"),
        },
    }


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        route = self.path.split("?", 1)[0]
        if route == '/api/footfall':
            config = read_json(PROJECT_ROOT / 'config.example.json')
            storage = config.get('storage', {})
            zone = storage.get('timezone', 'Asia/Calcutta')
            day = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('date', [datetime.now(resolve_timezone(zone)).date().isoformat()])[0]
            camera_id = config.get('doorway', {}).get('camera_id', 'entrance-fixed-2') + ':presence-person-v1'
            try:
                data = hourly_footfall(storage.get('database', str(PROJECT_ROOT / 'data/events.sqlite3')), day, camera_id, zone)
            except ValueError:
                self.send_error(400, 'Invalid date; expected YYYY-MM-DD')
                return
            except (sqlite3.Error, OSError):
                self.send_error(503, 'Entrance event history unavailable')
                return
            payload = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if route == "/api/live.mjpg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            last_sequence = -1
            last_frame_at = time.monotonic()
            try:
                while time.monotonic() - last_frame_at < 5:
                    part = live_part(PREVIEW_PATH, LIVE_METADATA_PATH, last_sequence)
                    if part is None:
                        time.sleep(0.02)
                        continue
                    self.wfile.write(part)
                    self.wfile.flush()
                    sequence_header = part.split(b"X-Frame-Sequence: ", 1)[1].split(b"\r\n", 1)[0]
                    last_sequence = int(sequence_header)
                    last_frame_at = time.monotonic()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        if route == "/api/status":
            payload = json.dumps(build_status()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if route == "/api/detection.jpg":
            try:
                payload = DETECTION_PATH.read_bytes()
            except OSError:
                self.send_error(503, "Model result frame is not available")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if route == "/api/frame.jpg":
            try:
                if datetime.now().timestamp() - PREVIEW_PATH.stat().st_mtime > 3:
                    self.send_error(503, "Camera frame is stale")
                    return
            except OSError:
                self.send_error(503, "Live camera frame is not available")
                return
            try:
                payload = PREVIEW_PATH.read_bytes()
            except OSError:
                self.send_error(503, "Live camera frame is not available")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local entrance dashboard")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    handler = partial(DashboardHandler, directory=str(WEB_ROOT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Entrance dashboard listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
