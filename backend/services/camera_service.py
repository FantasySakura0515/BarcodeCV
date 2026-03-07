from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from ..camera.base import CameraSource
from ..camera.opencv_source import OpenCVCameraSource
from ..camera.picamera_source import PiCameraSource
from .detection_service import DetectionPreviewResult, DetectionRunResult, DetectionService

logger = logging.getLogger("barcodecv.camera")


@dataclass
class CameraInfo:
    id: str
    label: str
    source_type: str
    camera_num: int
    width: int
    height: int
    available: bool
    status: str | None = None


class CameraService:
    def __init__(self, config: dict, detection_service: DetectionService):
        self._config = config
        self._detection_service = detection_service

    def list_cameras(self) -> list[CameraInfo]:
        cameras: list[CameraInfo] = []
        seen_ids: set[str] = set()

        for role, cfg in self._config.get("cameras", {}).items():
            camera_id = role
            info = self._probe_configured_camera(camera_id, role, cfg)
            cameras.append(info)
            seen_ids.add(camera_id)

        for index in range(5):
            camera_id = f"opencv-{index}"
            if camera_id in seen_ids:
                continue

            available, status = self._probe_opencv(index)
            if available:
                cameras.append(
                    CameraInfo(
                        id=camera_id,
                        label=f"USB / OpenCV Camera {index}",
                        source_type="opencv",
                        camera_num=index,
                        width=1280,
                        height=720,
                        available=True,
                        status=status,
                    )
                )

        return cameras

    def capture_preview(self, camera_id: str, max_width: int | None = None, quality: int = 70) -> bytes:
        with self._create_camera_source(camera_id) as camera:
            frame = camera.capture_frame()

        image = self._resize_to_max_width(frame.image, max_width)

        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), max(30, min(quality, 90))])
        if not ok:
            raise RuntimeError("無法編碼鏡頭畫面")
        return encoded.tobytes()

    def capture_and_detect(self, camera_id: str, model_type: str = "opencv") -> DetectionRunResult:
        with self._create_camera_source(camera_id) as camera:
            frame = camera.capture_frame()

        return self._detection_service.run_detection_on_image(
            image=frame.image,
            filename=f"{camera_id}.jpg",
            model_type=model_type,
            image_source="camera",
            camera_id=frame.camera_id,
        )

    def preview_and_detect(
        self,
        camera_id: str,
        model_type: str = "opencv",
        max_width: int | None = None,
    ) -> DetectionPreviewResult:
        with self._create_camera_source(camera_id) as camera:
            frame = camera.capture_frame()

        image = self._resize_to_max_width(frame.image, max_width)

        return self._detection_service.preview_detection_on_image(
            image=image,
            filename=f"{camera_id}.jpg",
            model_type=model_type,
            image_source="camera-preview",
            camera_id=frame.camera_id,
            save_preview_image=False,
        )

    @staticmethod
    def _resize_to_max_width(image: np.ndarray, max_width: int | None) -> np.ndarray:
        if not max_width or max_width <= 0:
            return image

        height, width = image.shape[:2]
        if width <= max_width:
            return image

        scale = max_width / float(width)
        resized_height = max(1, int(height * scale))
        return cv2.resize(image, (max_width, resized_height), interpolation=cv2.INTER_AREA)

    def _probe_configured_camera(self, camera_id: str, role: str, cfg: dict) -> CameraInfo:
        source_type = cfg.get("type", "picamera")
        camera_num = int(cfg.get("camera_num", 0))
        width = int(cfg.get("width", 1280))
        height = int(cfg.get("height", 720))

        try:
            available, status = self._probe_by_type(source_type, camera_num)
        except Exception as exc:
            available = False
            status = str(exc)

        return CameraInfo(
            id=camera_id,
            label=f"{role.title()} Camera",
            source_type=source_type,
            camera_num=camera_num,
            width=width,
            height=height,
            available=available,
            status=status,
        )

    def _probe_by_type(self, source_type: str, camera_num: int) -> tuple[bool, str | None]:
        if source_type == "opencv":
            return self._probe_opencv(camera_num)

        try:
            source = PiCameraSource(camera_num=camera_num)
            source.open()
            frame = source.capture_frame()
            source.close()
            return True, f"{frame.resolution[0]}x{frame.resolution[1]}"
        except Exception as exc:
            logger.info("Picamera probe failed for camera %s: %s", camera_num, exc)
            return False, str(exc)

    def _probe_opencv(self, camera_num: int) -> tuple[bool, str | None]:
        source = OpenCVCameraSource(camera_num=camera_num)
        try:
            source.open()
            frame = source.capture_frame()
            return True, f"{frame.resolution[0]}x{frame.resolution[1]}"
        except Exception as exc:
            return False, str(exc)
        finally:
            source.close()

    def _create_camera_source(self, camera_id: str) -> CameraSource:
        if camera_id.startswith("opencv-"):
            index = int(camera_id.split("-", 1)[1])
            return OpenCVCameraSource(camera_num=index, camera_id=camera_id)

        cfg = self._config.get("cameras", {}).get(camera_id)
        if cfg is None:
            raise ValueError("找不到指定鏡頭")

        source_type = cfg.get("type", "picamera")
        camera_num = int(cfg.get("camera_num", 0))
        width = int(cfg.get("width", 1280))
        height = int(cfg.get("height", 720))

        if source_type == "opencv":
            return OpenCVCameraSource(
                camera_num=camera_num,
                width=width,
                height=height,
                camera_id=camera_id,
            )

        return PiCameraSource(
            camera_num=camera_num,
            width=width,
            height=height,
            camera_id=camera_id,
        )