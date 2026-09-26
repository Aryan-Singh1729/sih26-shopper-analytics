"""One-shot probe for the exact full-person model on the board-local server."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


MODEL_ID = "person-detection-euioa/1"


def diagnostic_boxes(payload: dict) -> list[dict]:
    fields = ("class", "x", "y", "width", "height", "confidence")
    return [{key: prediction.get(key) for key in fields} for prediction in payload["predictions"]]


def probe_model(jpeg: bytes, base_url: str, model_id: str, api_key: str, include_boxes: bool = False) -> dict:
    query = urllib.parse.urlencode({"api_key": api_key, "confidence": 0.35})
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{model_id}?{query}",
        data=base64.b64encode(jpeg),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            status = response.status
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"model server returned HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("model server unavailable") from None
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise RuntimeError("model response lacks a predictions list")
    result = {
        "model_id": model_id,
        "http_status": status,
        "classes": sorted({str(p.get("class", "")) for p in predictions}),
        "box_count": len(predictions),
        "latency_ms": round((time.monotonic() - started) * 1000, 1),
    }
    if include_boxes:
        result["boxes"] = diagnostic_boxes(payload)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jpeg", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:9001")
    parser.add_argument("--boxes", action="store_true", help="include anonymous model box geometry")
    args = parser.parse_args(argv)
    key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not key:
        print("ROBOFLOW_API_KEY is not set", file=sys.stderr)
        return 2
    try:
        result = probe_model(Path(args.jpeg).read_bytes(), args.base_url, MODEL_ID, key, include_boxes=args.boxes)
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
