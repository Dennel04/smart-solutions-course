"""Thin, bounded HTTP client for the official ``mg400-base`` server."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


class MG400Error(RuntimeError):
    """The HTTP API failed or reported a robot state that forbids motion."""


class MG400Client:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        network_timeout: float = 2.0,
        poll_interval: float = 0.05,
        session: requests.Session | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if network_timeout <= 0 or poll_interval <= 0:
            raise ValueError("timeouts and poll interval must be positive")
        self.base_url = base_url.rstrip("/")
        self.network_timeout = network_timeout
        self.poll_interval = poll_interval
        self.session = session or requests.Session()
        self._monotonic = monotonic
        self._sleep = sleep

    def _request(
        self,
        method: str,
        path: str,
        *,
        require_ok: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.network_timeout,
                **kwargs,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise MG400Error(
                f"mg400-base request failed: {method} {path}: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise MG400Error(f"mg400-base returned non-object JSON for {method} {path}")
        if body.get("ok") is False or (require_ok and body.get("ok") is not True):
            detail = body.get("error") or "ok was not true"
            raise MG400Error(f"mg400-base rejected {method} {path}: {detail}")
        return body

    @staticmethod
    def require_safe_status(status: dict[str, Any]) -> None:
        """Reject every documented unsafe state; never enable the robot here."""
        if status.get("ok") is False:
            raise MG400Error("MG400 status is not ok")
        if status.get("connected") is not True:
            raise MG400Error("MG400 is not connected; use Connect in mg400-base")
        if status.get("enabled") is not True:
            raise MG400Error("MG400 is disabled; use Connect and Enable in mg400-base")
        if "feedback_ok" in status and status.get("feedback_ok") is not True:
            raise MG400Error("MG400 feedback is not healthy")
        if "servo_active" in status and status.get("servo_active") is not True:
            raise MG400Error("MG400 servo follower is not active")
        if (
            status.get("error")
            or status.get("fault")
            or status.get("fault_kind")
            or status.get("fault_label")
        ):
            detail = (
                status.get("fault_label")
                or status.get("fault_kind")
                or status.get("fault")
                or "robot error"
            )
            raise MG400Error(f"MG400 fault: {detail}")
        for field in ("link_error", "servo_error"):
            if status.get(field):
                raise MG400Error(f"MG400 {field}: {status[field]}")
        if status.get("stalled") is True:
            raise MG400Error("MG400 is stalled")
        MG400Client.pose_from_status(status)

    @staticmethod
    def pose_from_status(status: dict[str, Any]) -> tuple[float, float, float, float]:
        pose = status.get("pose")
        if not isinstance(pose, (list, tuple)) or len(pose) < 4:
            raise MG400Error("MG400 status has no valid pose")
        try:
            values = tuple(float(value) for value in pose[:4])
        except (TypeError, ValueError) as exc:
            raise MG400Error("MG400 status pose must contain numbers") from exc
        if not all(math.isfinite(value) for value in values):
            raise MG400Error("MG400 status pose must contain finite numbers")
        return values  # type: ignore[return-value]

    def get_status(self) -> dict[str, Any]:
        # The real mg400-base status object predates the common {"ok": ...}
        # envelope. Missing "ok" is valid here; an explicit false is not.
        return self._request("GET", "/api/status", require_ok=False)

    def set_speed(self, ratio: float) -> dict[str, Any]:
        return self._request("POST", "/api/speed", json={"ratio": ratio})

    def move(self, x: float, y: float, z: float, r: float) -> dict[str, Any]:
        target = (x, y, z, r)
        result = self._request(
            "POST", "/api/move", json={"x": x, "y": y, "z": z, "r": r}
        )
        clamped = result.get("clamped")
        if not isinstance(clamped, dict):
            raise MG400Error("mg400-base move response has no clamped target")
        try:
            actual = tuple(float(clamped[axis]) for axis in ("x", "y", "z", "r"))
        except (KeyError, TypeError, ValueError) as exc:
            raise MG400Error("mg400-base returned an invalid clamped target") from exc
        # mg400-base rounds its reported target to two decimal places.
        if not all(
            math.isfinite(value) and abs(value - requested) <= 0.01
            for value, requested in zip(actual, target)
        ):
            raise MG400Error("MG400 target was clamped; drawing stopped")
        return result

    def stop(self) -> dict[str, Any]:
        return self._request("POST", "/api/stop")

    def move_and_wait(
        self,
        x: float,
        y: float,
        z: float,
        r: float,
        *,
        tolerance: float = 0.5,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        if tolerance <= 0 or timeout <= 0:
            raise ValueError("tolerance and timeout must be positive")
        target = (float(x), float(y), float(z), float(r))
        self.move(*target)
        deadline = self._monotonic() + timeout
        while True:
            status = self.get_status()
            self.require_safe_status(status)
            pose = self.pose_from_status(status)
            if all(
                abs(actual - wanted) <= tolerance
                for actual, wanted in zip(pose, target)
            ):
                return status
            if self._monotonic() >= deadline:
                try:
                    self.stop()
                except MG400Error as exc:
                    LOGGER.warning("best-effort MG400 stop failed: %s", exc)
                raise MG400Error(f"MG400 move timed out after {timeout:g} s")
            self._sleep(self.poll_interval)
