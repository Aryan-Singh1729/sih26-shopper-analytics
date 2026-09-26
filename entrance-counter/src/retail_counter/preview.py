from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .types import Detection


def detection_label(confidence: float) -> str:
    return f"PERSON {confidence:.0%}"


def write_detection_preview(jpeg: bytes, detections: list[Detection], destination: Path) -> None:
    """Keep one annotated model-result frame in RAM for visual verification."""
    with Image.open(io.BytesIO(jpeg)) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for detection in detections:
        x1, y1, x2, y2 = (round(value) for value in detection.xyxy)
        draw.rectangle((x1, y1, x2, y2), outline=(84, 224, 155), width=4)
        label = detection_label(detection.confidence)
        top = max(0, y1 - 18)
        draw.rectangle((x1, top, x1 + 85, top + 18), fill=(9, 16, 14))
        draw.text((x1 + 4, top + 3), label, fill=(84, 224, 155), font=font)
    with tempfile.NamedTemporaryFile(suffix=".jpg", dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
        image.save(handle, format="JPEG", quality=78)
    os.replace(temporary, destination)
