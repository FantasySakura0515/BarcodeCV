import logging

from .base import CameraSource, Frame
from .picamera_source import PiCameraSource

logger = logging.getLogger("barcodecv.camera")


class CameraManager:
    """Manages the single Picamera2 source used by the CamArray flow."""

    def __init__(self, camera: CameraSource):
        self._camera = camera

    @staticmethod
    def from_config(config: dict) -> "CameraManager":
        """Create CameraManager from YAML config."""
        camera_cfg = config["cameras"]["main"]

        camera = PiCameraSource(
            camera_num=camera_cfg["camera_num"],
            width=camera_cfg["width"],
            height=camera_cfg["height"],
            camera_id="main",
        )
        return CameraManager(camera=camera)

    def open_all(self) -> None:
        self._camera.open()
        logger.info("Camera opened")

    def close_all(self) -> None:
        self._camera.close()
        logger.info("Camera closed")

    def capture(self) -> Frame:
        """Capture a frame from the aggregated CamArray device."""
        return self._camera.capture_frame()

    @property
    def camera(self) -> CameraSource:
        return self._camera

    def __enter__(self):
        self.open_all()
        return self

    def __exit__(self, *args):
        self.close_all()
