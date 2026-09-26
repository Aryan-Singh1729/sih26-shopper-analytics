import threading

from retail_counter.camera import LatestFrameCamera, extract_jpegs


def test_extract_jpeg_across_chunks():
    buffer = bytearray(b"noise\xff")
    assert extract_jpegs(buffer) == []
    assert buffer == b"\xff"
    buffer.extend(b"\xd8body\xff")
    assert extract_jpegs(buffer) == []
    buffer.extend(b"\xd9\xff\xd8next\xff\xd9")
    assert extract_jpegs(buffer) == [b"\xff\xd8body\xff\xd9", b"\xff\xd8next\xff\xd9"]
    assert buffer == b""


def test_motion_candidate_is_read_before_newer_live_frame():
    camera = object.__new__(LatestFrameCamera)
    camera._condition = threading.Condition()
    camera._stopped = False
    camera._candidate = (10, 1000.0, b"candidate")
    camera.candidate_processed = 0
    camera._latest = (20, 1001.0, b"latest")
    first = camera.read_after(0)
    second = camera.read_after(first.sequence)
    assert first.sequence == 10
    assert first.jpeg == b"candidate"
    assert second.sequence == 20
    assert second.jpeg == b"latest"
