import io

import numpy as np
from PIL import Image

from retail_counter.app import filter_person_detections, person_boxes_payload
from retail_counter.scene import SceneMonitor
from retail_counter.types import Detection


def frame_and_scene(tmp_path, changed=True):
    reference = tmp_path / "empty.npy"
    np.save(reference, np.full((90, 160), 90, dtype=np.uint8))
    scene = SceneMonitor(reference)
    frame = np.full((720, 1280), 90, dtype=np.uint8)
    if changed:
        frame[100:650, 300:700] = 180
    output = io.BytesIO()
    Image.fromarray(frame).save(output, format="JPEG", quality=90)
    return output.getvalue(), scene


def test_full_person_box_is_accepted(tmp_path):
    jpeg, scene = frame_and_scene(tmp_path)
    person = Detection((300, 100, 700, 650), 0.9)
    assert filter_person_detections([person], jpeg, 1280, 720, (0.15, 0.12, 0.8, 0.88), scene, 0.02) == [person]
    assert person_boxes_payload([person]) == [
        {"class": "person", "xyxy": [300, 100, 700, 650], "confidence": 0.9}
    ]


def test_each_image_edge_rejects_clipped_person(tmp_path):
    jpeg, scene = frame_and_scene(tmp_path)
    boxes = [(0, 100, 700, 650), (300, 0, 700, 650), (300, 100, 1279, 650), (300, 100, 700, 719)]
    for box in boxes:
        assert filter_person_detections([Detection(box, 0.9)], jpeg, 1280, 720, (0, 0, 1, 1), scene, 0.02) == []


def test_static_background_and_empty_output_are_rejected(tmp_path):
    jpeg, scene = frame_and_scene(tmp_path, changed=False)
    person = Detection((300, 100, 700, 650), 0.9)
    assert filter_person_detections([person], jpeg, 1280, 720, (0, 0, 1, 1), scene, 0.02) == []
    assert filter_person_detections([], jpeg, 1280, 720, (0, 0, 1, 1), scene, 0.02) == []
