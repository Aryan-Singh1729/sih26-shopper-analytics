import pytest

from deployment.benchmark_yolox_person import parse_edge_impulse_response, summarize_candidate


def test_summary_rejects_empty_samples():
    with pytest.raises(ValueError, match="samples"):
        summarize_candidate([])


def test_summary_reports_person_boxes_and_latency():
    samples = [
        {"latency_ms": 100, "rss_mb": 50, "detections": []},
        {"latency_ms": 200, "rss_mb": 60, "detections": [
            {"class": "person", "confidence": 0.9, "bounding_box_xyxy": [10, 20, 100, 200]},
        ]},
        {"latency_ms": 300, "rss_mb": 55, "detections": [
            {"class": "chair", "confidence": 0.8, "bounding_box_xyxy": [1, 2, 3, 4]},
        ]},
    ]
    result = summarize_candidate(samples)
    assert result == {
        "samples": 3, "p50_latency_ms": 200, "p95_latency_ms": 290,
        "effective_fps": 5.0, "classes": ["chair", "person"],
        "person_box_count": 1, "peak_rss_mb": 60,
    }


def test_summary_rejects_unlocated_person_proposal():
    with pytest.raises(ValueError, match="bounding_box_xyxy"):
        summarize_candidate([{"latency_ms": 100, "rss_mb": 50, "detections": [
            {"class": "person", "confidence": 0.9},
        ]}])


def test_parser_converts_edge_impulse_boxes_to_original_xyxy():
    payload = {"result": {"bounding_boxes": [
        {"label": "person", "value": 0.75, "x": 100, "y": 20, "width": 150, "height": 400},
    ], "resized": {"originalWidth": 1280, "originalHeight": 720}}}
    assert parse_edge_impulse_response(payload) == [
        {"class": "person", "confidence": 0.75, "bounding_box_xyxy": [100, 20, 250, 420]},
    ]


def test_parser_rejects_missing_geometry():
    with pytest.raises(ValueError, match="width"):
        parse_edge_impulse_response({"result": {"bounding_boxes": [
            {"label": "person", "value": 0.75, "x": 100, "y": 20, "height": 400},
        ]}})
