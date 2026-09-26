import json
import urllib.error

import pytest

from deployment.probe_person_model import probe_model, main, diagnostic_boxes


def test_probe_returns_response_without_exposing_key(monkeypatch, capsys):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"predictions": [{"class": "person", "x": 4}]}).encode()

    def fake_open(request, timeout):
        assert request.full_url.startswith("http://127.0.0.1:9001/person-detection-euioa/1?")
        assert request.data == b"anBlZw=="
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    result = probe_model(b"jpeg", "http://127.0.0.1:9001", "person-detection-euioa/1", "secret-key")
    assert result["classes"] == ["person"]
    assert result["box_count"] == 1
    assert result["http_status"] == 200
    assert "secret-key" not in str(result) + capsys.readouterr().out


def test_probe_unavailable_server_hides_key(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise urllib.error.URLError("secret-key network error")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    with pytest.raises(RuntimeError, match="unavailable") as error:
        probe_model(b"jpeg", "http://127.0.0.1:9001", "person-detection-euioa/1", "secret-key")
    assert "secret-key" not in str(error.value)


def test_cli_requires_environment_key(monkeypatch, capsys):
    monkeypatch.delenv("ROBOFLOW_API_KEY", raising=False)
    assert main(["--jpeg", "unused.jpg"]) == 2
    assert "ROBOFLOW_API_KEY" in capsys.readouterr().err


def test_diagnostic_boxes_reports_geometry_without_credentials():
    payload = {"predictions": [
        {"class": "person", "x": 400, "y": 300, "width": 200, "height": 500, "confidence": 0.87, "detection_id": "abc"},
    ]}
    boxes = diagnostic_boxes(payload)
    assert boxes == [{"class": "person", "x": 400, "y": 300, "width": 200, "height": 500, "confidence": 0.87}]


def test_probe_can_include_diagnostic_boxes(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"predictions": [{"class": "person", "x": 400, "y": 300, "width": 200, "height": 500, "confidence": 0.87}]}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    result = probe_model(b"jpeg", "http://127.0.0.1:9001", "person-detection-euioa/1", "secret-key", include_boxes=True)
    assert result["boxes"] == [{"class": "person", "x": 400, "y": 300, "width": 200, "height": 500, "confidence": 0.87}]
    assert "secret-key" not in str(result)
