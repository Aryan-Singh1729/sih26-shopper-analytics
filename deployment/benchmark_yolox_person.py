"""Summarize local YOLOX-Nano probe observations without retaining frames."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import numpy as np


def parse_edge_impulse_response(payload: dict) -> list[dict]:
    boxes = payload["result"]["bounding_boxes"]
    detections = []
    for box in boxes:
        for field in ("x", "y", "width", "height"):
            if field not in box:
                raise ValueError(f"detection lacks {field}")
        x, y = float(box["x"]), float(box["y"])
        width, height = float(box["width"]), float(box["height"])
        detections.append({
            "class": str(box["label"]),
            "confidence": float(box["value"]),
            "bounding_box_xyxy": [x, y, x + width, y + height],
        })
    return detections


def summarize_candidate(samples: list[dict]) -> dict:
    if not samples:
        raise ValueError("samples cannot be empty")
    latencies = [float(sample["latency_ms"]) for sample in samples]
    classes: set[str] = set()
    person_boxes = 0
    for sample in samples:
        for detection in sample["detections"]:
            class_name = str(detection["class"])
            classes.add(class_name)
            if class_name == "person":
                box = detection.get("bounding_box_xyxy")
                if not isinstance(box, (list, tuple)) or len(box) != 4:
                    raise ValueError("person detection lacks bounding_box_xyxy")
                person_boxes += 1
    return {
        "samples": len(samples),
        "p50_latency_ms": float(np.percentile(latencies, 50)),
        "p95_latency_ms": float(np.percentile(latencies, 95)),
        "effective_fps": 1000 / float(np.mean(latencies)),
        "classes": sorted(classes),
        "person_box_count": person_boxes,
        "peak_rss_mb": max(float(sample["rss_mb"]) for sample in samples),
    }


def _infer(jpeg: bytes, url: str) -> dict:
    boundary = "retail-edge-probe"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + jpeg + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _container_memory_mb(name: str) -> float:
    output = subprocess.check_output(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name],
        text=True, timeout=15,
    ).split("/", 1)[0].strip()
    value, unit = output[:-3], output[-3:]
    return float(value) * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[unit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jpeg", type=Path, default=Path("/dev/shm/retail-edge-live.jpg"))
    parser.add_argument("--url", default="http://127.0.0.1:1337/api/image")
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    if args.frames < 1 or args.warmup < 0:
        parser.error("frames must be positive and warmup non-negative")
    samples = []
    for index in range(args.frames + args.warmup):
        jpeg = args.jpeg.read_bytes()
        started = time.monotonic()
        detections = parse_edge_impulse_response(_infer(jpeg, args.url))
        latency_ms = (time.monotonic() - started) * 1000
        if index >= args.warmup:
            samples.append({"latency_ms": latency_ms, "rss_mb": 0, "detections": detections})
    memory_mb = _container_memory_mb("retail-yolox-probe")
    for sample in samples:
        sample["rss_mb"] = memory_mb
    print(json.dumps(summarize_candidate(samples), sort_keys=True))


if __name__ == "__main__":
    main()
