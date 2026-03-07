import logging
from datetime import datetime

import numpy as np

from .base import CameraSource, Frame

logger = logging.getLogger("barcodecv.camera")


class PiCameraSource(CameraSource):
    """Camera source using Picamera2 for Raspberry Pi CSI cameras."""

    def __init__(
        self,
        camera_num: int = 0,
        width: int = 1920,
        height: int = 1080,
        camera_id: str | None = None,
    ):
        self._camera_num = camera_num
        self._width = width
        self._height = height
        self._camera_id = camera_id or f"picam{camera_num}"
        self._picam = None

    def open(self) -> None:
        from picamera2 import Picamera2

        self._picam = Picamera2(camera_num=self._camera_num)
        config = self._picam.create_video_configuration(
            main={"size": (self._width, self._height), "format": "BGR888"}
        )
        self._picam.configure(config)
        self._picam.start()

        # Enable continuous autofocus if supported (e.g. imx708).
        # libcamera Python bindings may not be available in all venv setups,
        # so we import them here and treat any failure as "no autofocus".
        try:
            from libcamera import controls  # noqa: PLC0415

            self._picam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
            logger.info("Autofocus enabled for PiCamera %d", self._camera_num)
        except Exception:  # ImportError, RuntimeError, KeyError, etc.
            logger.info("Autofocus not available for PiCamera %d (manual lens or no libcamera bindings)", self._camera_num)

        logger.info(
            "Opened PiCamera %d (%s) at %dx%d",
            self._camera_num,
            self._camera_id,
            self._width,
            self._height,
        )

    def close(self) -> None:
        if self._picam is not None:
            try:
                self._picam.stop()
            except Exception as exc:
                logger.warning("Error stopping PiCamera %d: %s", self._camera_num, exc)
            try:
                self._picam.close()
            except Exception as exc:
                logger.warning("Error closing PiCamera %d: %s", self._camera_num, exc)
            self._picam = None
            logger.info("Closed PiCamera %d (%s)", self._camera_num, self._camera_id)

    def capture_frame(self) -> Frame:
        if self._picam is None:
            raise RuntimeError(f"Camera {self._camera_id} is not open")

        # capture_array() with BGR888 main stream → HxWx3 numpy array (B, G, R)
        # Picamera2 occasionally returns 4-channel XBGR even when BGR888 is
        # requested (driver quirk), so strip the alpha channel when needed.
        raw = self._picam.capture_array()
        if raw.ndim == 3 and raw.shape[2] == 4:
            bgr_array = raw[:, :, :3]
        else:
            bgr_array = raw

        return Frame(
            image=bgr_array,
            timestamp=datetime.now(),
            camera_id=self._camera_id,
            resolution=(self._width, self._height),
        )

    def is_open(self) -> bool:
        return self._picam is not None

    def get_resolution(self) -> tuple[int, int]:
        return (self._width, self._height)

    def set_resolution(self, width: int, height: int) -> None:
        was_open = self.is_open()
        if was_open:
            self.close()
        self._width = width
        self._height = height
        if was_open:
            self.open()

    @staticmethod
    def available_cameras() -> list[dict]:
        """Non-invasive camera enumeration via Picamera2.global_camera_info().

        Returns a list of dicts, e.g.::

            [{"Id": "...", "Num": 0, "Model": "imx708"}, ...]

        Returns an empty list if picamera2 is not installed or no camera found.
        """
        try:
            from picamera2 import Picamera2

            infos = Picamera2.global_camera_info()
            logger.debug("Picamera2.global_camera_info() = %s", infos)
            return infos
        except Exception as exc:  # noqa: BLE001
            logger.debug("global_camera_info failed: %s", exc)
            return []
