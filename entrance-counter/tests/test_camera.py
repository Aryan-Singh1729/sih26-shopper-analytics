import json
import time

from retail_counter.camera import publish_live_frame


def test_publisher_replaces_frame_and_metadata_with_newest_sequence(tmp_path):
    jpeg = tmp_path / "live.jpg"
    metadata = tmp_path / "live-meta.json"
    now = time.time()
    publish_live_frame(jpeg, metadata, b"first", 7, now - 0.1)
    publish_live_frame(jpeg, metadata, b"second", 8, now)
    details = json.loads(metadata.read_text())
    assert jpeg.read_bytes() == b"second"
    assert details["sequence"] == 8
    assert details["captured_at"] == now
    assert details["jpeg_mtime_ns"] == jpeg.stat().st_mtime_ns
def test_small_live_preview_keeps_original_capture_dimensions(tmp_path):
    import io
    from PIL import Image
    from retail_counter.camera import LatestFrameCamera
    camera = LatestFrameCamera.__new__(LatestFrameCamera)
    camera.width = 1280
    camera.live_width = 640
    camera.live_quality = 70
    camera.live_path = tmp_path / 'live.jpg'
    camera.live_metadata_path = tmp_path / 'meta.json'
    buffer = io.BytesIO()
    Image.new('RGB', (1280, 720)).save(buffer, format='JPEG')
    camera._publish_live(buffer.getvalue(), 1, 100)
    assert Image.open(camera.live_path).size == (640, 360)
    assert camera.width == 1280

