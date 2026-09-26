import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployment"))
from track_continuity import EmptyViewGate, advance_tracks, reconcile_tracks


def test_refresh_keeps_existing_visit_identity():
    old = [{"box": (100, 100, 80, 180), "confirmed": 0.0, "visit_id": "first"}]
    detected = [{"box": (108, 104, 82, 178), "confirmed": 0.4}]
    tracks = reconcile_tracks(old, detected, now=0.5)
    assert len(tracks) == 1
    assert tracks[0]["visit_id"] == "first"
    assert tracks[0]["box"] == detected[0]["box"]


def test_missing_detection_retains_box_for_three_seconds_then_hides_it():
    old = [{"box": (100, 100, 80, 180), "confirmed": 0.0, "visit_id": "first"}]
    assert len(reconcile_tracks(old, [], now=2.9)) == 1
    assert reconcile_tracks(old, [], now=3.1) == []


def test_two_people_reassociate_one_to_one_and_newcomer_stays_new():
    old = [
        {"box": (100, 100, 80, 180), "confirmed": 0.0, "visit_id": "left"},
        {"box": (400, 100, 80, 180), "confirmed": 0.0, "visit_id": "right"},
    ]
    detected = [
        {"box": (405, 100, 80, 180), "confirmed": 0.5},
        {"box": (105, 100, 80, 180), "confirmed": 0.5},
        {"box": (700, 100, 80, 180), "confirmed": 0.5},
    ]
    tracks = reconcile_tracks(old, detected, now=0.6)
    assert [track.get("visit_id") for track in tracks] == ["right", "left", None]


def test_failed_visual_tracker_keeps_last_box_until_prediction_limit():
    class LostTracker:
        def update(self, _image):
            return False, None

    old = [{"tracker": LostTracker(), "box": (100, 100, 80, 180), "confirmed": 0.0, "visit_id": "first"}]
    held = advance_tracks(old, image=None, now=2.9)
    assert len(held) == 1
    assert held[0]["box"] == (100, 100, 80, 180)
    assert held[0]["predicted"] is True
    assert advance_tracks(old, image=None, now=3.1) == []


def test_successful_visual_tracking_survives_detector_gap_and_keeps_visit():
    class MovingTracker:
        def update(self,_image):return True,(110,100,80,180)

    old=[{'tracker':MovingTracker(),'box':(100,100,80,180),'confirmed':0.0,'visit_id':'first'}]
    tracked=advance_tracks(old,image=None,now=4.0)
    assert len(tracked)==1
    assert tracked[0]['predicted'] is False
    assert tracked[0]['box']==(110,100,80,180)
    refreshed=reconcile_tracks(tracked,[{'box':(112,100,80,180),'confirmed':4.1}],now=4.2)
    assert refreshed[0]['visit_id']=='first'


def test_rearm_requires_two_seconds_of_fresh_empty_results():
    gate = EmptyViewGate(2.0)
    assert gate.observe(0.0, 1, False) is False
    assert gate.observe(3.0, 0, True) is False
    assert gate.observe(4.0, 0, False) is False
    assert gate.observe(5.0, 0, True) is False
    assert gate.observe(7.1, 0, True) is True
    assert gate.observe(7.2, 1, False) is False
