from __future__ import annotations

import os
from collections import deque
from pathlib import Path

import numpy as np

from .types import PerformanceSnapshot


class Metrics:
    def __init__(self):
        self.inference_ms: deque[float] = deque(maxlen=300)
        self.end_to_end_ms: deque[float] = deque(maxlen=300)
        self.processed_times: deque[float] = deque(maxlen=300)
        self.last_sequence = 0
        self.dropped_frames = 0
        self._last_cpu_total: int | None = None
        self._last_cpu_idle: int | None = None

    def record(self, sequence: int, processed_at: float, inference_ms: float, captured_at: float) -> None:
        if self.last_sequence and sequence > self.last_sequence + 1:
            self.dropped_frames += sequence - self.last_sequence - 1
        self.last_sequence = sequence
        self.processed_times.append(processed_at)
        self.inference_ms.append(inference_ms)
        self.end_to_end_ms.append(max(0.0, (processed_at - captured_at) * 1000))

    def snapshot(self, visible_tracks: int) -> PerformanceSnapshot:
        duration = self.processed_times[-1] - self.processed_times[0] if len(self.processed_times) > 1 else 0
        fps = (len(self.processed_times) - 1) / duration if duration > 0 else 0.0
        memory = self._memory()
        return PerformanceSnapshot(
            processed_fps=fps,
            inference_ms_p50=self._percentile(self.inference_ms, 50),
            inference_ms_p95=self._percentile(self.inference_ms, 95),
            end_to_end_ms_p95=self._percentile(self.end_to_end_ms, 95),
            dropped_frames=self.dropped_frames,
            visible_tracks=visible_tracks,
            rss_mb=memory[0],
            available_memory_mb=memory[1],
            cpu_percent=self._cpu(),
            temperature_c=self._temperature(),
        )

    @staticmethod
    def _percentile(values, percentile: int) -> float:
        return float(np.percentile(values, percentile)) if values else 0.0

    @staticmethod
    def _memory() -> tuple[float, float]:
        rss_pages = int(Path("/proc/self/statm").read_text().split()[1])
        rss_mb = rss_pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
        fields = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            fields[key] = int(value.strip().split()[0])
        return rss_mb, fields.get("MemAvailable", 0) / 1024

    def _cpu(self) -> float:
        values = [int(value) for value in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        idle, total = values[3] + values[4], sum(values)
        result = 0.0
        if self._last_cpu_total is not None and total > self._last_cpu_total:
            result = 100.0 * (1 - (idle - self._last_cpu_idle) / (total - self._last_cpu_total))
        self._last_cpu_total, self._last_cpu_idle = total, idle
        return result

    @staticmethod
    def _temperature() -> float | None:
        values = []
        for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
            try:
                raw = float(path.read_text().strip())
                values.append(raw / 1000 if raw > 1000 else raw)
            except (OSError, ValueError):
                continue
        return max(values) if values else None

