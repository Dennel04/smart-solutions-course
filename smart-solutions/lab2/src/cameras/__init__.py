"""Local-only Lab 2 camera sources."""

from .base import CameraFrame, CameraSource
from .mock_camera import MockCamera
from .usb_camera import UsbCamera, UsbCameraConfig
from .xiao_camera import XiaoCamera, XiaoCameraConfig

__all__ = [
    "CameraFrame",
    "CameraSource",
    "MockCamera",
    "UsbCamera",
    "UsbCameraConfig",
    "XiaoCamera",
    "XiaoCameraConfig",
]
