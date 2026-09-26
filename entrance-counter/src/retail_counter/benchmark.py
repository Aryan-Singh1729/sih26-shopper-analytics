from __future__ import annotations

import argparse
import json
import statistics
import time

from .camera import LatestFrameCamera
from .config import load_config
from .detector import create_detector


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the configured local detector and camera")
    parser.add_argument("--config", required=True)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    config = load_config(args.config)
    detector = create_detector(config.model)
    camera = LatestFrameCamera(config.camera)
    latencies: list[float] = []
    detection_counts: list[int] = []
    sequence = 0
    try:
        for index in range(args.frames + args.warmup):
            frame = camera.read_after(sequence, timeout=5)
            if frame is None:
                raise RuntimeError("camera frame timeout")
            sequence = frame.sequence
            started = time.perf_counter()
            detections = detector.infer(frame.image)
            elapsed_ms = (time.perf_counter() - started) * 1000
            if index >= args.warmup:
                latencies.append(elapsed_ms)
                detection_counts.append(len(detections))
    finally:
        camera.close()
        detector.close()
    result = {
        "model": detector.metadata,
        "frames": len(latencies),
        "latency_ms": {
            "mean": statistics.fmean(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
        },
        "effective_fps": 1000.0 / statistics.fmean(latencies),
        "detections": {
            "total": sum(detection_counts),
            "minimum_per_frame": min(detection_counts, default=0),
            "maximum_per_frame": max(detection_counts, default=0),
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
