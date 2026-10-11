"""Shared single-worker camera source abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any

from .metrics import CameraMetrics


@dataclass(frozen=True)
class CameraFrame:
    jpeg: bytes
    width: int
    height: int
    counter: int
    captured_at: str
    captured_monotonic: float


class CameraSource(ABC):
    """One capture worker shared by every browser consumer."""

    def __init__(
        self,
        name: str,
        *,
        target_fps: float,
        retry_interval_s: float = 1.0,
        clock=time.monotonic,
    ) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be positive")
        if retry_interval_s <= 0:
            raise ValueError("retry_interval_s must be positive")
        self.name = name
        self.target_fps = float(target_fps)
        self.retry_interval_s = float(retry_interval_s)
        self._clock = clock
        self.metrics = CameraMetrics(clock=clock)
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame: CameraFrame | None = None
        self._state = "stopped"
        self._error: str | None = None

    @property
    def worker_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._condition:
            if self.worker_alive:
                return
            self._stop_event.clear()
            self._state = "starting"
            self._error = None
            self._thread = threading.Thread(
                target=self._run,
                name=f"camera-{self.name}",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        with self._condition:
            self._state = "stopped" if not self.worker_alive else "stop_timeout"
            self._thread = None if not self.worker_alive else thread

    def get_frame(
        self, *, after_counter: int | None = None, timeout: float = 1.0
    ) -> CameraFrame | None:
        deadline = self._clock() + max(0.0, timeout)
        with self._condition:
            while not self._stop_event.is_set():
                if self._frame is not None and (
                    after_counter is None or self._frame.counter > after_counter
                ):
                    return self._frame
                remaining = deadline - self._clock()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            return None

    def record_served(self, byte_count: int) -> None:
        self.metrics.served(byte_count)

    def status(self) -> dict[str, Any]:
        with self._condition:
            frame = self._frame
            state = self._state
            error = self._error
        return {
            "name": self.name,
            "state": state,
            "available": frame is not None and state == "running",
            "error": error,
            "resolution": None
            if frame is None or frame.width <= 0 or frame.height <= 0
            else {"width": frame.width, "height": frame.height},
            "target_fps": self.target_fps,
            "last_frame": None
            if frame is None
            else {
                "counter": frame.counter,
                "captured_at": frame.captured_at,
            },
            "metrics": self.metrics.snapshot(),
            "configuration": self.configuration(),
        }

    def _publish(self, jpeg: bytes, width: int, height: int) -> None:
        if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
            raise ValueError("camera frame is not a complete JPEG")
        counter = self.metrics.captured()
        frame = CameraFrame(
            jpeg=jpeg,
            width=width,
            height=height,
            counter=counter,
            captured_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            captured_monotonic=self._clock(),
        )
        with self._condition:
            self._frame = frame
            self._state = "running"
            self._error = None
            self._condition.notify_all()

    def _set_error(self, error: Exception) -> None:
        with self._condition:
            # Never present the last good image as if it were current after a
            # source failure. Recovery will publish a fresh frame.
            self._frame = None
            self._state = "unavailable"
            self._error = f"{type(error).__name__}: {error}"[:240]
            self._condition.notify_all()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            resource = None
            try:
                resource = self.open_source()
                while not self._stop_event.is_set():
                    started = self._clock()
                    jpeg, width, height = self.capture_frame(resource)
                    self._publish(jpeg, width, height)
                    frame_period = 1.0 / self.target_fps
                    self._stop_event.wait(max(0.0, frame_period - (self._clock() - started)))
            except Exception as exc:
                self._set_error(exc)
            finally:
                if resource is not None:
                    try:
                        self.close_source(resource)
                    except Exception as exc:
                        self._set_error(exc)
            if not self._stop_event.is_set():
                self._stop_event.wait(self.retry_interval_s)
        with self._condition:
            self._state = "stopped"
            self._condition.notify_all()

    @abstractmethod
    def open_source(self) -> object: ...

    @abstractmethod
    def capture_frame(self, resource: object) -> tuple[bytes, int, int]: ...

    @abstractmethod
    def close_source(self, resource: object) -> None: ...

    @abstractmethod
    def configuration(self) -> dict[str, Any]: ...
