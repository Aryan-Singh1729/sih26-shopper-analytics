from retail_counter.tracker import ByteTracker
from retail_counter.types import Detection


def test_tracker_keeps_identity_and_separates_people():
    tracker = ByteTracker({
        "high_threshold": 0.5,
        "low_threshold": 0.1,
        "new_track_threshold": 0.5,
        "match_iou": 0.1,
        "low_match_iou": 0.1,
        "track_buffer_seconds": 1.5,
        "minimum_hits": 2,
    })
    first = tracker.update([Detection((0, 0, 20, 20), 0.9), Detection((80, 0, 100, 20), 0.9)], 1.0)
    second = tracker.update([Detection((2, 1, 22, 21), 0.9), Detection((78, 1, 98, 21), 0.9)], 1.1)
    assert [track.track_id for track in first] == [1, 2]
    assert [track.track_id for track in second] == [1, 2]
    assert all(track.confirmed for track in second)


def test_low_confidence_detection_preserves_existing_track():
    tracker = ByteTracker({
        "high_threshold": 0.5,
        "low_threshold": 0.1,
        "new_track_threshold": 0.5,
        "match_iou": 0.1,
        "low_match_iou": 0.1,
        "track_buffer_seconds": 1.5,
        "minimum_hits": 2,
    })
    tracker.update([Detection((0, 0, 20, 20), 0.9)], 1.0)
    tracks = tracker.update([Detection((1, 0, 21, 20), 0.3)], 1.1)
    assert len(tracks) == 1
    assert tracks[0].track_id == 1

