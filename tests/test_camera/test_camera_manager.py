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

    def test_capture_global_and_local(self):
        global_cam = self._make_mock_camera("global")
        local_cam = self._make_mock_camera("local")

        manager = CameraManager(global_camera=global_cam, local_camera=local_cam)

        g_frame = manager.capture_global()
        assert g_frame.camera_id == "global"

        l_frame = manager.capture_local()
        assert l_frame.camera_id == "local"

    def test_context_manager(self):
        global_cam = self._make_mock_camera("global")
        local_cam = self._make_mock_camera("local")

        manager = CameraManager(global_camera=global_cam, local_camera=local_cam)

        with manager:
            global_cam.open.assert_called_once()
            local_cam.open.assert_called_once()

        global_cam.close.assert_called_once()
        local_cam.close.assert_called_once()
