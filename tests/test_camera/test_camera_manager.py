from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from backend.camera.base import Frame
from backend.camera.camera_manager import CameraManager


class TestCameraManager:
    def _make_mock_camera(self, camera_id: str) -> MagicMock:
        cam = MagicMock()
        cam.capture_frame.return_value = Frame(
            image=np.zeros((480, 640, 3), dtype=np.uint8),
            timestamp=datetime.now(),
            camera_id=camera_id,
            resolution=(640, 480),
        )
        return cam

    def test_capture_returns_main_frame(self):
        camera = self._make_mock_camera("main")

        manager = CameraManager(camera=camera)

        frame = manager.capture()
        assert frame.camera_id == "main"

    def test_context_manager(self):
        camera = self._make_mock_camera("main")

        manager = CameraManager(camera=camera)

        with manager:
            camera.open.assert_called_once()

        camera.close.assert_called_once()
