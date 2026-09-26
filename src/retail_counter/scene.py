from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
from PIL import Image


def thumbnail(jpeg: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(jpeg)) as image:
        gray = image.convert("L").resize((160, 90), Image.Resampling.BILINEAR)
        return np.asarray(gray, dtype=np.uint8)


class SceneMonitor:
    """Compare the current camera view with an explicitly captured empty view."""

    def __init__(self, baseline_path: Path, changed_fraction_threshold: float = 0.025):
        self.baseline = np.load(baseline_path, allow_pickle=False).astype(np.int16)
        if self.baseline.shape != (90, 160):
            raise ValueError("empty scene reference has the wrong shape")
        self.threshold = changed_fraction_threshold

    def changed_fraction(self, jpeg: bytes) -> float:
        current = thumbnail(jpeg).astype(np.int16)
        difference = current - self.baseline
        difference -= int(np.median(difference))
        # Focus on the central/lower part where a visitor can appear.
        region = np.abs(difference[20:90, 48:136])
        return float(np.mean(region >= 35))

    def box_changed_fraction(
        self,
        jpeg: bytes,
        xyxy: tuple[float, float, float, float],
        image_size: tuple[int, int],
    ) -> float:
        current = thumbnail(jpeg).astype(np.int16)
        difference = current - self.baseline
        difference -= int(np.median(difference))
        width, height = image_size
        if width <= 0 or height <= 0:
            return 0.0
        x1, y1, x2, y2 = xyxy
        left = max(0, min(159, int(x1 * 160 / width)))
        top = max(0, min(89, int(y1 * 90 / height)))
        right = max(left + 1, min(160, int(np.ceil(x2 * 160 / width))))
        bottom = max(top + 1, min(90, int(np.ceil(y2 * 90 / height))))
        return float(np.mean(np.abs(difference[top:bottom, left:right]) >= 35))

    def occupied(self, jpeg: bytes) -> tuple[bool, float]:
        score = self.changed_fraction(jpeg)
        return score >= self.threshold, score


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a low-resolution empty-scene reference")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    if args.reference:
        monitor = SceneMonitor(args.reference)
        occupied, score = monitor.occupied(args.source.read_bytes())
        print(f"scene_changed_fraction={score:.4f} occupied={occupied}")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        reference = thumbnail(args.source.read_bytes())
        np.save(args.output, reference, allow_pickle=False)
        print(f"Saved empty-scene reference: {args.output}")
    else:
        parser.error("either --output or --reference is required")


if __name__ == "__main__":
    main()
