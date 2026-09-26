from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    raw: dict[str, Any]

    @property
    def camera(self) -> dict[str, Any]:
        return self.raw["camera"]

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def tracking(self) -> dict[str, Any]:
        return self.raw["tracking"]

    @property
    def doorway(self) -> dict[str, Any]:
        return self.raw["doorway"]

    @property
    def storage(self) -> dict[str, Any]:
        return self.raw["storage"]

    @property
    def runtime(self) -> dict[str, Any]:
        return self.raw["runtime"]


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    required = {"camera", "model", "tracking", "doorway", "storage", "runtime"}
    missing = required.difference(raw)
    if missing:
        raise ConfigError(f"missing configuration sections: {sorted(missing)}")
    roi = raw["camera"].get("detection_roi", [0, 0, 1, 1])
    if len(roi) != 4 or not all(isinstance(value, (int, float)) for value in roi):
        raise ConfigError("camera.detection_roi must contain four normalized numbers")
    left, top, right, bottom = roi
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ConfigError("camera.detection_roi must be [left, top, right, bottom] within [0, 1]")
    doorway = raw["doorway"]
    for key in ("outside_line", "inside_line", "corridor_polygon"):
        if key not in doorway:
            raise ConfigError(f"doorway.{key} is required")
    if len(doorway["outside_line"]) != 2 or len(doorway["inside_line"]) != 2:
        raise ConfigError("doorway lines must each contain exactly two normalized points")
    for points in (doorway["outside_line"], doorway["inside_line"], doorway["corridor_polygon"]):
        for x, y in points:
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ConfigError("doorway coordinates must be normalized to [0, 1]")
    if len(doorway["corridor_polygon"]) < 3:
        raise ConfigError("doorway.corridor_polygon must contain at least three points")
    return AppConfig(raw)
