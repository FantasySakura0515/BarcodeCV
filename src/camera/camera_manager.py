import logging

from .base import CameraSource, Frame
from .picamera_source import PiCameraSource

logger = logging.getLogger("barcodecv.camera")


class CameraManager:
    """Manages dual CSI cameras for Global-to-Local strategy."""

    def __init__(self, global_camera: CameraSource, local_camera: CameraSource):
        self._global = global_camera
        self._local = local_camera

    @staticmethod
    def from_config(config: dict) -> "CameraManager":
        """Create CameraManager from YAML config."""
        global_cfg = config["cameras"]["global"]
        local_cfg = config["cameras"]["local"]

        global_cam = PiCameraSource(
            camera_num=global_cfg["camera_num"],
            width=global_cfg["width"],
            height=global_cfg["height"],
            camera_id="global",
        )
        local_cam = PiCameraSource(
            camera_num=local_cfg["camera_num"],
            width=local_cfg["width"],
            height=local_cfg["height"],
            camera_id="local",
        )

        return CameraManager(global_camera=global_cam, local_camera=local_cam)

    def open_all(self) -> None:
        self._global.open()
        self._local.open()
        logger.info("All cameras opened")

    def close_all(self) -> None:
        self._global.close()
        self._local.close()
        logger.info("All cameras closed")

    def capture_global(self) -> Frame:
        """Capture a wide-angle frame for DataMatrix detection."""
        return self._global.capture_frame()

    def capture_local(self) -> Frame:
        """Capture a high-resolution frame for DataMatrix decoding."""
        return self._local.capture_frame()

    @property
    def global_camera(self) -> CameraSource:
        return self._global

    @property
    def local_camera(self) -> CameraSource:
        return self._local

    def __enter__(self):
        self.open_all()
        return self

    def __exit__(self, *args):
        self.close_all()
