import logging
import subprocess
from datetime import datetime

import cv2
import numpy as np

from .base import CameraSource, Frame

logger = logging.getLogger("barcodecv.camera")

# Formats tried in order of preference (picamera2 main-stream formats).
# BGR888  → 3-ch BGR, no conversion needed
# XBGR8888 → 4-ch XBGR, drop 4th channel
# RGB888  → 3-ch RGB, swap to BGR
_PROBE_FORMATS = ["BGR888", "XBGR8888", "RGB888"]


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
        self._fmt: str = "BGR888"  # format successfully negotiated in open()
        self._rotation: int = 0    # degrees (0, 90, 180, 270); set from camera info

    def open(self) -> None:
        from picamera2 import Picamera2

        # Read rotation from global_camera_info before opening
        try:
            infos = Picamera2.global_camera_info()
            for info in infos:
                if info.get("Num") == self._camera_num:
                    self._rotation = int(info.get("Rotation", 0))
                    logger.info(
                        "PiCamera %d rotation from metadata: %d°",
                        self._camera_num,
                        self._rotation,
                    )
                    break
        except Exception:
            pass  # non-fatal; will use rotation=0

        self._picam = Picamera2(camera_num=self._camera_num)

        # Try each format until the camera accepts one.
        last_exc: Exception | None = None
        for fmt in _PROBE_FORMATS:
            try:
                config = self._picam.create_video_configuration(
                    main={"size": (self._width, self._height), "format": fmt}
                )
                self._picam.configure(config)
                self._fmt = fmt
                logger.debug("PiCamera %d accepted format %s", self._camera_num, fmt)
                break
            except Exception as exc:
                last_exc = exc
                logger.debug("PiCamera %d rejected format %s: %s", self._camera_num, fmt, exc)
        else:
            # None of the formats worked — give up
            raise RuntimeError(
                f"鏡頭 {self._camera_num} 無法配置任何已知格式 {_PROBE_FORMATS}: {last_exc}"
            )

        self._picam.start()

        # Enable continuous autofocus if supported (e.g. imx708).
        # libcamera Python bindings may not be available in all venv setups,
        # so we import them here and treat any failure as "no autofocus".
        try:
            from libcamera import controls  # noqa: PLC0415

            self._picam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
            logger.info("Autofocus enabled for PiCamera %d", self._camera_num)
        except Exception:  # ImportError, RuntimeError, KeyError, etc.
            logger.info(
                "Autofocus not available for PiCamera %d (manual lens or no libcamera bindings)",
                self._camera_num,
            )

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

        raw = self._picam.capture_array()

        # Normalise to BGR based on the format negotiated in open().
        if raw.ndim == 3 and raw.shape[2] == 4:
            # XBGR8888 — drop the padding/alpha channel, result is BGR
            bgr_array = raw[:, :, :3]
        elif self._fmt == "RGB888":
            # RGB → BGR for OpenCV compatibility
            bgr_array = raw[:, :, ::-1].copy()
        else:
            # BGR888 (or unknown 3-channel): use as-is
            bgr_array = raw

        # Correct for physical camera rotation reported by libcamera
        if self._rotation == 180:
            bgr_array = cv2.rotate(bgr_array, cv2.ROTATE_180)
        elif self._rotation == 90:
            bgr_array = cv2.rotate(bgr_array, cv2.ROTATE_90_CLOCKWISE)
        elif self._rotation == 270:
            bgr_array = cv2.rotate(bgr_array, cv2.ROTATE_90_COUNTERCLOCKWISE)

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
        """Non-invasive camera enumeration.

        Tries (in order):
        1. ``Picamera2.global_camera_info()`` — fast, no device open required.
        2. ``libcamera-hello --list-cameras`` via subprocess — works even when
           the picamera2 Python package is not in the active venv (e.g. system
           install only).

        Returns a list of dicts with at least ``"Num"`` and ``"Model"`` keys,
        or an empty list if no CSI cameras are detected at all.
        """
        # --- Strategy 1: picamera2 Python API ---
        try:
            from picamera2 import Picamera2  # noqa: PLC0415

            infos = Picamera2.global_camera_info()
            logger.debug("Picamera2.global_camera_info() = %s", infos)
            if infos:
                return infos
        except Exception as exc:  # noqa: BLE001
            logger.debug("global_camera_info failed: %s", exc)

        # --- Strategy 2: libcamera CLI subprocess ---
        try:
            result = subprocess.run(
                ["libcamera-hello", "--list-cameras"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout + result.stderr
            logger.debug("libcamera-hello output: %s", output)

            # Parse lines like:  "0 : imx708 [...]" or "Available cameras"
            cams: list[dict] = []
            for line in output.splitlines():
                line = line.strip()
                # Match "  0 : imx708 [...]"
                if line and line[0].isdigit() and " : " in line:
                    parts = line.split(" : ", 1)
                    num = int(parts[0].strip())
                    model = parts[1].split(" ")[0] if parts[1] else "unknown"
                    cams.append({"Num": num, "Model": model, "Id": f"libcam{num}"})
            if cams:
                logger.debug("libcamera-hello found cameras: %s", cams)
                return cams
        except FileNotFoundError:
            logger.debug("libcamera-hello not found (not running on RPi?)")
        except Exception as exc:  # noqa: BLE001
            logger.debug("libcamera-hello subprocess failed: %s", exc)

        return []

    @staticmethod
    def diagnose() -> dict:
        """Return a diagnostic dict useful for debugging camera issues."""
        info: dict = {}

        # picamera2 importability
        try:
            import picamera2  # noqa: PLC0415

            info["picamera2_version"] = getattr(picamera2, "__version__", "unknown")
            info["picamera2_path"] = picamera2.__file__
        except ImportError as exc:
            info["picamera2_import_error"] = str(exc)

        # libcamera importability
        try:
            import libcamera  # noqa: PLC0415

            info["libcamera_version"] = getattr(libcamera, "__version__", "unknown")
        except ImportError as exc:
            info["libcamera_import_error"] = str(exc)

        # global_camera_info result
        try:
            from picamera2 import Picamera2  # noqa: PLC0415

            info["global_camera_info"] = Picamera2.global_camera_info()
        except Exception as exc:  # noqa: BLE001
            info["global_camera_info_error"] = str(exc)

        # libcamera-hello CLI
        try:
            result = subprocess.run(
                ["libcamera-hello", "--list-cameras"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            info["libcamera_hello_stdout"] = result.stdout
            info["libcamera_hello_stderr"] = result.stderr
            info["libcamera_hello_returncode"] = result.returncode
        except FileNotFoundError:
            info["libcamera_hello_error"] = "libcamera-hello not found"
        except Exception as exc:  # noqa: BLE001
            info["libcamera_hello_error"] = str(exc)

        # v4l2 devices
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--list-devices"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            info["v4l2_devices"] = result.stdout or result.stderr
        except FileNotFoundError:
            info["v4l2_error"] = "v4l2-ctl not found"
        except Exception as exc:  # noqa: BLE001
            info["v4l2_error"] = str(exc)

        return info
