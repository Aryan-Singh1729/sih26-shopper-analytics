from retail_counter.presence import PresenceCounter
from retail_counter.types import Detection


def test_arrival_counts_once_until_view_clears():
    counter = PresenceCounter({"camera_id": "door", "clear_observations": 2, "clear_seconds": 5}, "Asia/Calcutta")
    person = Detection((10, 10, 30, 30), 0.9)
    assert len(counter.update([person], 1000)) == 1
    assert counter.update([person], 1003) == []
    assert counter.update([], 1006, False) == []
    assert counter.update([person], 1009) == []
    assert counter.update([], 1012, False) == []
    assert counter.update([], 1018, False) == []
    assert len(counter.update([person], 1021)) == 1


def test_empty_view_does_not_count():
    counter = PresenceCounter({"camera_id": "door"}, "Asia/Calcutta")
    assert counter.update([], 1000) == []


def test_arrival_uses_separate_camera_id_from_older_counting_mode():
    counter = PresenceCounter({"camera_id": "door"}, "Asia/Calcutta")
    assert counter.camera_id == "door:presence-person-v1"


def test_model_dropout_does_not_rearm_while_scene_is_occupied():
    counter = PresenceCounter({"camera_id": "door", "clear_observations": 2, "clear_seconds": 3}, "Asia/Calcutta")
    person = Detection((10, 10, 30, 30), 0.9)
    assert len(counter.update([person], 1000, True)) == 1
    assert counter.update([], 1010, True) == []
    assert counter.update([person], 1020, True) == []
    assert counter.update([], 1025, False) == []
    assert counter.update([], 1029, False) == []
    assert len(counter.update([person], 1032, True)) == 1


def test_rearms_after_sustained_relative_scene_clear_when_baseline_drifts():
    counter = PresenceCounter({"camera_id": "door", "clear_observations": 3, "clear_seconds": 4,
                               "clear_scene_drop": 0.05}, "Asia/Calcutta")
    person = Detection((100, 100, 300, 600), 0.9)
    assert len(counter.update([person], 1000, True, 0.27)) == 1
    assert counter.update([], 1003, True, 0.26) == []
    assert counter.update([person], 1006, True, 0.25) == []
    assert counter.update([], 1010, True, 0.20) == []
    assert counter.update([], 1013, True, 0.19) == []
    assert counter.update([], 1016, True, 0.20) == []
    assert counter.present is False
    assert len(counter.update([person], 1020, True, 0.28)) == 1
