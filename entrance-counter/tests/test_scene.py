import io

import numpy as np
from PIL import Image

from retail_counter.scene import SceneMonitor


def jpeg(image):
    output = io.BytesIO()
    Image.fromarray(image).save(output, format="JPEG", quality=90)
    return output.getvalue()


def test_scene_monitor_ignores_small_global_lighting_change_but_sees_person(tmp_path):
    reference = np.full((90, 160), 90, dtype=np.uint8)
    path = tmp_path / "empty.npy"
    np.save(path, reference)
    monitor = SceneMonitor(path)
    brighter = np.full((90, 160), 96, dtype=np.uint8)
    assert monitor.occupied(jpeg(brighter))[0] is False
    occupied = brighter.copy()
    occupied[35:75, 70:105] = 200
    seen, score = monitor.occupied(jpeg(occupied))
    assert seen is True
    assert score > 0.025


def test_box_change_rejects_static_door_and_accepts_changed_head_area(tmp_path):
    reference = np.full((90, 160), 90, dtype=np.uint8)
    path = tmp_path / "empty.npy"
    np.save(path, reference)
    monitor = SceneMonitor(path)
    empty_frame = np.full((720, 1280), 90, dtype=np.uint8)
    assert monitor.box_changed_fraction(jpeg(empty_frame), (450, 250, 580, 420), (1280, 720)) < 0.01
    occupied_frame = empty_frame.copy()
    occupied_frame[250:420, 450:580] = 200
    assert monitor.box_changed_fraction(jpeg(occupied_frame), (450, 250, 580, 420), (1280, 720)) > 0.8
