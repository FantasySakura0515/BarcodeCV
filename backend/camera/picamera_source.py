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
        from libcamera import controls
        from picamera2 import Picamera2

        self._picam = Picamera2(camera_num=self._camera_num)
        config = self._picam.create_video_configuration(
            main={"size": (self._width, self._height), "format": "BGR888"}
        )
        self._picam.configure(config)
        self._picam.start()

        # Enable continuous autofocus if supported (e.g. imx708)
        try:
            self._picam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
            logger.info("Autofocus enabled for PiCamera %d", self._camera_num)
        except (RuntimeError, KeyError):
            logger.info("Autofocus not available for PiCamera %d (manual lens)", self._camera_num)

        logger.info(
            "Opened PiCamera %d (%s) at %dx%d",
            self._camera_num,
            self._camera_id,
            self._width,
            self._height,
        )

    def close(self) -> None:
        if self._picam is not None:
            self._picam.stop()
            self._picam.close()
            self._picam = None
            logger.info("Closed PiCamera %d (%s)", self._camera_num, self._camera_id)

    def capture_frame(self) -> Frame:
        if self._picam is None:
            raise RuntimeError(f"Camera {self._camera_id} is not open")

        # BGR888 format — already OpenCV compatible, no channel swap needed
        bgr_array = self._picam.capture_array()

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
