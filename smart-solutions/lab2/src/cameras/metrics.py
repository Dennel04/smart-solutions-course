"""Thread-safe software counters for camera capture and HTTP serving."""

from __future__ import annotations

import threading
import time


class CameraMetrics:
    def __init__(self, *, clock=time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self._lock = threading.Lock()
        self._captured = 0
        self._served = 0
        self._bytes_served = 0

    def captured(self) -> int:
        with self._lock:
            self._captured += 1
            return self._captured

    def served(self, byte_count: int) -> None:
        with self._lock:
            self._served += 1
            self._bytes_served += max(0, byte_count)

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            uptime = max(0.0, self._clock() - self._started)
            divisor = max(uptime, 1e-9)
            return {
                "frames_captured": self._captured,
                "frames_served": self._served,
                "bytes_served": self._bytes_served,
                "uptime_s": round(uptime, 3),
                "capture_fps": round(self._captured / divisor, 3),
                "served_fps": round(self._served / divisor, 3),
                "bytes_per_s": round(self._bytes_served / divisor, 3),
                "mbit_per_s": round(self._bytes_served * 8 / divisor / 1_000_000, 6),
            }
