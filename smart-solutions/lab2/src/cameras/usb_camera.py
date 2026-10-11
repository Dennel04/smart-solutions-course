"""OpenCV USB camera backend with one shared capture worker."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .base import CameraSource


@dataclass(frozen=True)
class UsbCameraConfig:
    device: int | str = 0
    capture_width: int = 3840
    capture_height: int = 2160
    stream_width: int = 1280
    stream_height: int = 720
    target_fps: float = 10.0
    jpeg_quality: int = 80
    retry_interval_s: float = 2.0


class UsbCamera(CameraSource):
    def __init__(self, config: UsbCameraConfig, *, cv2_module: Any = None) -> None:
        super().__init__(
            "table",
            target_fps=config.target_fps,
            retry_interval_s=config.retry_interval_s,
        )
        self.config = config
        self._cv2 = cv2_module

    def _opencv(self):
        if self._cv2 is not None:
            return self._cv2
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("opencv-python-headless is not installed") from exc
        self._cv2 = cv2
        return cv2

    def open_source(self) -> object:
        cv2 = self._opencv()
        capture = cv2.VideoCapture(self.config.device)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("USB camera is unavailable")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.capture_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.capture_height)
        capture.set(cv2.CAP_PROP_FPS, self.config.target_fps)
        return capture

    def capture_frame(self, resource: object) -> tuple[bytes, int, int]:
        cv2 = self._opencv()
        ok, frame = resource.read()
        if not ok or frame is None:
            raise RuntimeError("USB camera frame read failed")
        if self.config.stream_width > 0 and self.config.stream_height > 0:
            frame = cv2.resize(
                frame,
                (self.config.stream_width, self.config.stream_height),
            )
        ok, encoded = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality]
        )
        if not ok:
            raise RuntimeError("USB camera JPEG encoding failed")
        height, width = frame.shape[:2]
        return encoded.tobytes(), int(width), int(height)

    def close_source(self, resource: object) -> None:
        resource.release()

    def configuration(self) -> dict[str, object]:
        return {"backend": "opencv-usb", **asdict(self.config)}
