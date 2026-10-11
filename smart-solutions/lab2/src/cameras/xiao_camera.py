"""Configurable XIAO ESP32S3 Sense JPEG snapshot client."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen

from .base import CameraSource


@dataclass(frozen=True)
class XiaoCameraConfig:
    snapshot_url: str = ""
    expected_width: int = 0
    expected_height: int = 0
    target_fps: float = 5.0
    request_timeout_s: float = 2.0
    retry_interval_s: float = 2.0
    max_frame_bytes: int = 5_000_000


class XiaoCamera(CameraSource):
    def __init__(
        self,
        config: XiaoCameraConfig,
        *,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        super().__init__(
            "tool",
            target_fps=config.target_fps,
            retry_interval_s=config.retry_interval_s,
        )
        self.config = config
        self._opener = opener

    def open_source(self) -> object:
        if not self.config.snapshot_url:
            raise RuntimeError("XIAO snapshot URL is not configured")
        if not self.config.snapshot_url.startswith(("http://", "https://")):
            raise RuntimeError("XIAO snapshot URL must use HTTP or HTTPS")
        return self

    def capture_frame(self, resource: object) -> tuple[bytes, int, int]:
        request = Request(
            self.config.snapshot_url,
            headers={"Accept": "image/jpeg", "User-Agent": "lab2-local-station/1"},
        )
        response = self._opener(request, timeout=self.config.request_timeout_s)
        try:
            data = response.read(self.config.max_frame_bytes + 1)
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
        if len(data) > self.config.max_frame_bytes:
            raise RuntimeError("XIAO JPEG exceeds configured size limit")
        if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
            raise RuntimeError("XIAO response is not a complete JPEG")
        return data, self.config.expected_width, self.config.expected_height

    def close_source(self, resource: object) -> None:
        return None

    def configuration(self) -> dict[str, object]:
        values = asdict(self.config)
        # A future deployment URL may contain credentials or private query
        # parameters, so status responses expose only whether it is present.
        values.pop("snapshot_url")
        values["snapshot_url_configured"] = bool(self.config.snapshot_url)
        return {"backend": "xiao-http-snapshot", **values}
