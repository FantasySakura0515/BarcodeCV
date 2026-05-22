from __future__ import annotations

import sys
from datetime import datetime

import cv2

from .base import CameraSource, Frame


class OpenCVCameraSource(CameraSource):
    """Generic camera source backed by OpenCV VideoCapture."""

    def __init__(
        self,
        camera_num: int = 0,
        width: int = 1280,
        height: int = 720,
        camera_id: str | None = None,
    ):
        self._camera_num = camera_num
        self._width = width
        self._height = height
        self._camera_id = camera_id or f"opencv-{camera_num}"
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        capture = cv2.VideoCapture(self._camera_num, backend)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"無法開啟鏡頭 index={self._camera_num}")

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._capture = capture

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def capture_frame(self) -> Frame:
        if self._capture is None:
            raise RuntimeError(f"Camera {self._camera_id} is not open")

        ok, image = self._capture.read()
        if not ok or image is None:
            raise RuntimeError(f"無法從鏡頭 {self._camera_id} 取得畫面")

        height, width = image.shape[:2]
        return Frame(
            image=image,
            timestamp=datetime.now(),
            camera_id=self._camera_id,
            resolution=(width, height),
        )

    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def get_resolution(self) -> tuple[int, int]:
        return (self._width, self._height)

    def set_resolution(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        if self._capture is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)