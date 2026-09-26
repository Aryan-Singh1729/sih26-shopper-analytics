import pytest
from retail_counter.yolox_detector import YoloxPersonDetector
from retail_counter.detector import DetectorError


def test_only_confident_person_boxes_are_returned_in_original_coordinates():
    detector = YoloxPersonDetector({"confidence": 0.5})
    boxes = [
        {"label": "person", "value": 0.9, "x": 100, "y": 20, "width": 150, "height": 400},
        {"label": "person", "value": 0.32, "x": 300, "y": 20, "width": 50, "height": 100},
        {"label": "bed", "value": 0.9, "x": 0, "y": 0, "width": 200, "height": 100},
    ]
    result = detector.parse_predictions({"result": {"bounding_boxes": boxes}}, 1280, 720)
    assert len(result) == 1
    assert result[0].xyxy == (100, 20, 250, 420)


def test_malformed_person_geometry_is_rejected():
    detector = YoloxPersonDetector({})
    with pytest.raises(DetectorError):
        detector.parse_predictions({"result": {"bounding_boxes": [
            {"label": "person", "value": 0.9, "x": float("nan"), "y": 0, "width": 10, "height": 20},
        ]}}, 1280, 720)
