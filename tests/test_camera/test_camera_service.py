from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from backend.camera.base import Frame
from backend.services import camera_service as camera_service_module
from backend.services.camera_service import CameraService


def test_probe_by_type_tries_picamera_direct_open_when_enumeration_is_empty(monkeypatch):
    service = CameraService(config={}, detection_service=MagicMock())
    probe_picamera = MagicMock(return_value=(True, "640x480"))

    monkeypatch.setattr(camera_service_module, "_is_picamera2_available", lambda: True)
    monkeypatch.setattr(camera_service_module, "_is_raspberry_pi", lambda: True)
    monkeypatch.setattr(camera_service_module.PiCameraSource, "available_cameras", staticmethod(lambda: []))
    monkeypatch.setattr(service, "_probe_picamera", probe_picamera)

    available, status = service._probe_by_type("arducam", 0)

    assert available is True
    assert status == "640x480"
    probe_picamera.assert_called_once_with(0, [])


def test_probe_picamera_falls_back_to_direct_open_when_enumeration_is_empty(monkeypatch):
    class FakePiCameraSource:
        instances: list["FakePiCameraSource"] = []

        def __init__(self, camera_num: int = 0, width: int = 1920, height: int = 1080, camera_id: str | None = None):
            self.camera_num = camera_num
            self.width = width
            self.height = height
            self.camera_id = camera_id or f"picam{camera_num}"
            self.closed = False
            FakePiCameraSource.instances.append(self)

        @staticmethod
        def available_cameras() -> list[dict]:
            return []

        def open(self) -> None:
            return None

        def capture_frame(self) -> Frame:
            return Frame(
                image=np.zeros((480, 640, 3), dtype=np.uint8),
                timestamp=datetime.now(),
                camera_id=self.camera_id,
                resolution=(640, 480),
            )

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(camera_service_module, "PiCameraSource", FakePiCameraSource)
    service = CameraService(config={}, detection_service=MagicMock())

    available, status = service._probe_picamera(1)

    assert available is True
    assert status == "640x480"
    assert FakePiCameraSource.instances[0].camera_num == 1
    assert FakePiCameraSource.instances[0].closed is True


def test_create_camera_source_allows_direct_picamera_open_when_enumeration_is_empty(monkeypatch):
    class FakePiCameraSource:
        def __init__(self, camera_num: int = 0, width: int = 1920, height: int = 1080, camera_id: str | None = None):
            self.camera_num = camera_num
            self.width = width
            self.height = height
            self.camera_id = camera_id

        @staticmethod
        def available_cameras() -> list[dict]:
            return []

    monkeypatch.setattr(camera_service_module, "PiCameraSource", FakePiCameraSource)
    monkeypatch.setattr(camera_service_module, "_is_picamera2_available", lambda: True)
    monkeypatch.setattr(camera_service_module, "_is_raspberry_pi", lambda: True)

    service = CameraService(
        config={
            "cameras": {
                "main": {
                    "type": "arducam",
                    "camera_num": 1,
                    "width": 1280,
                    "height": 720,
                    "allow_opencv_fallback": False,
                }
            }
        },
        detection_service=MagicMock(),
    )

    source = service._create_camera_source("main")

    assert isinstance(source, FakePiCameraSource)
    assert source.camera_num == 1
    assert source.width == 1280
    assert source.height == 720
    assert source.camera_id == "main"
