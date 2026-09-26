from retail_counter import web_server
from retail_counter.camera import publish_live_frame
import os
import time
import json
from datetime import datetime, timezone


def test_pc_health_uses_recent_success_without_network_poll(monkeypatch, tmp_path):
    status = tmp_path / 'status.json'
    monkeypatch.setattr(web_server, 'STATUS_PATH', status)
    def unexpected_network(*args, **kwargs):
        raise AssertionError('Status polling must not contact PC detector')
    monkeypatch.setattr(web_server.urllib.request, 'urlopen', unexpected_network)
    def write(age):
        status.write_text(json.dumps({'healthy': True, 'model': {'backend': 'PC ONNX Runtime CPU'},
                                     'detection': {'result_at': datetime.fromtimestamp(time.time()-age, timezone.utc).isoformat()}}))
    write(.1)
    assert web_server.inference_health()[0] is True
    write(4)
    assert web_server.inference_health()[0] is False


def test_build_status_uses_verified_model_when_counter_is_not_running(monkeypatch, tmp_path):
    verification = tmp_path / "verification.json"
    verification.write_text('{"inference":{"model_id":"person-detection-euioa/1","model_type":"Roboflow 3.0 Object Detection (Fast)"}}')
    monkeypatch.setattr(web_server, "STATUS_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(web_server, "VERIFICATION_PATH", verification)
    monkeypatch.setattr(web_server, "inference_health", lambda: (True, {"name": "server", "version": "1"}))
    payload = web_server.build_status()
    assert payload["counter_running"] is False
    assert payload["inference"]["healthy"] is True
    assert payload["model"]["model_id"] == "person-detection-euioa/1"


def test_live_snapshot_returns_newest_frame_not_backlog(tmp_path):
    jpeg = tmp_path / "live.jpg"
    metadata = tmp_path / "live-meta.json"
    now = time.time()
    publish_live_frame(jpeg, metadata, b"old", 1, now - 0.2)
    publish_live_frame(jpeg, metadata, b"new", 2, now)
    snapshot = web_server.read_live_snapshot(jpeg, metadata)
    assert snapshot[0] == b"new"
    assert snapshot[1]["sequence"] == 2
    assert snapshot[1]["captured_at"] == now


def test_live_snapshot_rejects_stale_or_mismatched_frame(tmp_path):
    jpeg = tmp_path / "live.jpg"
    metadata = tmp_path / "live-meta.json"
    publish_live_frame(jpeg, metadata, b"stale", 1, time.time() - 4)
    assert web_server.read_live_snapshot(jpeg, metadata) is None
    publish_live_frame(jpeg, metadata, b"fresh", 2, time.time())
    original_mtime = jpeg.stat().st_mtime_ns
    jpeg.write_bytes(b"other")
    os.utime(jpeg, ns=(original_mtime, original_mtime))
    assert web_server.read_live_snapshot(jpeg, metadata) is None


def test_live_part_uses_latest_sequence_and_capture_time(tmp_path):
    jpeg = tmp_path / "live.jpg"
    metadata = tmp_path / "live-meta.json"
    now = time.time()
    publish_live_frame(jpeg, metadata, b"latest", 5, now)
    payload = web_server.live_part(jpeg, metadata, last_sequence=1)
    assert payload is not None
    assert b"X-Frame-Sequence: 5\r\n" in payload
    assert f"X-Captured-At: {now}\r\n".encode() in payload
    assert payload.endswith(b"latest\r\n")
    assert web_server.live_part(jpeg, metadata, last_sequence=5) is None
