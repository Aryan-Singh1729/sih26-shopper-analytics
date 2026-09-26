import pytest

from retail_counter.detector import DetectorError, RoboflowInferenceDetector


def test_requires_environment_key(monkeypatch):
    monkeypatch.delenv("ROBOFLOW_API_KEY", raising=False)
    with pytest.raises(DetectorError, match="ROBOFLOW_API_KEY"):
        RoboflowInferenceDetector({"model_id": "person-detection-euioa/1"})


def test_rejects_model_substitution(monkeypatch):
    monkeypatch.setenv("ROBOFLOW_API_KEY", "test-only")
    with pytest.raises(DetectorError, match="exactly"):
        RoboflowInferenceDetector({"model_id": "some-other-model/1"})


def test_parses_person_predictions_to_clipped_xyxy():
    payload = {
        "predictions": [
            {"x": 10, "y": 80, "width": 40, "height": 20, "confidence": 0.9, "class": "person"}
        ]
    }
    detections = RoboflowInferenceDetector._parse_predictions(payload, 640, 480)
    assert len(detections) == 1
    assert detections[0].xyxy == (0.0, 70.0, 30.0, 90.0)
    assert detections[0].confidence == 0.9


def test_rejects_unexpected_nonempty_class_output():
    payload = {
        "predictions": [
            {"x": 100, "y": 80, "width": 40, "height": 20, "confidence": 0.9, "class": "head"}
        ]
    }
    with pytest.raises(DetectorError, match="unexpected model classes"):
        RoboflowInferenceDetector._parse_predictions(payload, 640, 480)


def test_exact_model_metadata_and_empty_predictions(monkeypatch):
    monkeypatch.setenv("ROBOFLOW_API_KEY", "test-only")
    detector = RoboflowInferenceDetector({"model_id": "person-detection-euioa/1", "expected_class": "person"})
    assert detector.metadata["model_id"] == "person-detection-euioa/1"
    assert detector.metadata["expected_class"] == "person"
    assert detector._parse_predictions({"predictions": []}, 640, 480) == []
