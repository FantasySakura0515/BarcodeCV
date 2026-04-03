from __future__ import annotations

import functools
import importlib.util
import logging
import sys
import threading
import time as _time
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from ..camera.base import CameraSource
from ..camera.opencv_source import OpenCVCameraSource
from ..camera.picamera_source import PiCameraSource
from .detection_service import DetectionPreviewResult, DetectionRunResult, DetectionService

logger = logging.getLogger("barcodecv.camera")

# ── Per-camera exclusive locks ──────────────────────────────────────────────
# Prevents two requests from calling open() on the same physical camera.
_CAMERA_LOCKS: dict[str, threading.Lock] = {}
_CAMERA_LOCKS_MU = threading.Lock()


def _get_camera_lock(camera_id: str) -> threading.Lock:
    with _CAMERA_LOCKS_MU:
        if camera_id not in _CAMERA_LOCKS:
            _CAMERA_LOCKS[camera_id] = threading.Lock()
        return _CAMERA_LOCKS[camera_id]


# ── Per-camera raw frame cache ──────────────────────────────────────────────
# Detection and capture both store the last captured numpy frame here.
# preview endpoint can serve from cache when camera is locked by detection,
# avoiding the "preview frozen while scanning" problem.
_FRAME_CACHE: dict[str, tuple[np.ndarray, float]] = {}  # camera_id -> (frame, monotonic_ts)
_FRAME_CACHE_MU = threading.Lock()
_FRAME_CACHE_MAX_AGE_S = 5.0  # serve cached frame up to 5 s stale


def _cache_frame(camera_id: str, frame: np.ndarray) -> None:
    with _FRAME_CACHE_MU:
        _FRAME_CACHE[camera_id] = (frame, _time.monotonic())


def _get_cached_frame(camera_id: str) -> np.ndarray | None:
    with _FRAME_CACHE_MU:
        entry = _FRAME_CACHE.get(camera_id)
    if entry is None:
        return None
    frame, ts = entry
    if _time.monotonic() - ts > _FRAME_CACHE_MAX_AGE_S:
        return None
    return frame


# ── Per-camera MJPEG stream registry ───────────────────────────────────────
# Tracks which cameras currently have an active MJPEG stream thread.
# Detection endpoints skip camera open/close and use the frame cache instead.
_ACTIVE_STREAMS: dict[str, bool] = {}
_ACTIVE_STREAMS_MU = threading.Lock()


def _is_streaming(camera_id: str) -> bool:
    with _ACTIVE_STREAMS_MU:
        return _ACTIVE_STREAMS.get(camera_id, False)


@functools.lru_cache(maxsize=1)
def _is_raspberry_pi() -> bool:
    if not sys.platform.startswith("linux"):
        return False

    model_paths = [
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    ]
    for model_path in model_paths:
        try:
            with open(model_path, "r", encoding="utf-8", errors="ignore") as model_file:
                if "raspberry pi" in model_file.read().lower():
                    return True
        except OSError:
            pass

    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as cpuinfo_file:
            cpuinfo = cpuinfo_file.read().lower()
            return "raspberry pi" in cpuinfo or "bcm27" in cpuinfo
    except OSError:
        return False


@functools.lru_cache(maxsize=1)
def _is_picamera2_available() -> bool:
    return importlib.util.find_spec("picamera2") is not None


def _rpi_picamera_dependency_message() -> str:
    return (
        "Raspberry Pi Arducam 需要 picamera2/libcamera。"
        "請在 Pi 上執行: sudo apt update && sudo apt install -y python3-picamera2 python3-libcamera libcamera-apps; "
        "若使用虛擬環境請執行 scripts/fix_venv_pi.sh 重新建立 --system-site-packages 的 .venv。"
    )


class _FallbackCameraSource(CameraSource):
    """Try primary backend first, then fallback backend if open() fails."""

    def __init__(
        self,
        *,
        camera_id: str,
        primary_name: str,
        fallback_name: str,
        primary_factory: Callable[[], CameraSource],
        fallback_factory: Callable[[], CameraSource],
    ):
        self._camera_id = camera_id
        self._primary_name = primary_name
        self._fallback_name = fallback_name
        self._primary_factory = primary_factory
        self._fallback_factory = fallback_factory
        self._active_source: CameraSource | None = None

    def open(self) -> None:
        primary = self._primary_factory()
        try:
            primary.open()
            self._active_source = primary
            return
        except Exception as primary_exc:
            try:
                primary.close()
            except Exception:
                pass

            logger.warning(
                "Camera %s primary backend (%s) failed: %s. Trying fallback (%s).",
                self._camera_id,
                self._primary_name,
                primary_exc,
                self._fallback_name,
            )

            fallback = self._fallback_factory()
            try:
                fallback.open()
                self._active_source = fallback
                return
            except Exception as fallback_exc:
                try:
                    fallback.close()
                except Exception:
                    pass

                raise RuntimeError(
                    f"鏡頭 {self._camera_id} 無法開啟: "
                    f"{self._primary_name}={primary_exc}; {self._fallback_name}={fallback_exc}"
                ) from fallback_exc

    def close(self) -> None:
        if self._active_source is not None:
            self._active_source.close()
            self._active_source = None

    def capture_frame(self):
        source = self._require_active_source()
        return source.capture_frame()

    def is_open(self) -> bool:
        return self._active_source is not None and self._active_source.is_open()

    def get_resolution(self) -> tuple[int, int]:
        source = self._require_active_source()
        return source.get_resolution()

    def set_resolution(self, width: int, height: int) -> None:
        source = self._require_active_source()
        source.set_resolution(width, height)

    def _require_active_source(self) -> CameraSource:
        if self._active_source is None:
            raise RuntimeError(f"Camera {self._camera_id} is not open")
        return self._active_source


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

    @staticmethod
    def _extract_picamera_numbers(available_cams: list[dict]) -> list[int]:
        numbers: list[int] = []
        for i, info in enumerate(available_cams):
            raw_num = info.get("Num", i)
            try:
                numbers.append(int(raw_num))
            except (TypeError, ValueError):
                numbers.append(i)
        return numbers

    def _resolve_picamera_num(self, configured_num: int, available_cams: list[dict] | None = None) -> tuple[int, bool, list[int]]:
        cams = available_cams if available_cams is not None else PiCameraSource.available_cameras()
        available_nums = self._extract_picamera_numbers(cams)

        if not available_nums:
            return configured_num, False, []

        if configured_num in available_nums:
            return configured_num, False, available_nums

        if 0 <= configured_num < len(available_nums):
            # Treat configured_num as ordinal index when actual Num values are
            # non-contiguous (common on some Arducam/libcamera stacks).
            resolved_num = available_nums[configured_num]
            return resolved_num, True, available_nums

        return configured_num, False, available_nums

    def list_cameras(self) -> list[CameraInfo]:
        cameras: list[CameraInfo] = []
        seen_ids: set[str] = set()

        for role, cfg in self._config.get("cameras", {}).items():
            camera_id = role
            info = self._probe_configured_camera(camera_id, role, cfg)
            cameras.append(info)
            seen_ids.add(camera_id)

        if self._should_probe_generic_opencv_slots():
            for index in range(10):
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

    def _should_probe_generic_opencv_slots(self) -> bool:
        system_cfg = self._config.get("system", {})
        explicit = system_cfg.get("probe_generic_opencv_cameras")
        if isinstance(explicit, bool):
            return explicit

        cameras_cfg = self._config.get("cameras", {})
        if cameras_cfg:
            # When the project already defines concrete camera roles
            # (global/local), avoid extra index probing unless explicitly enabled.
            return False

        if not _is_raspberry_pi():
            return True
        return False

    def capture_preview(self, camera_id: str, max_width: int | None = None, quality: int = 70) -> bytes:
        # When MJPEG stream is active, return the most recent cached frame instantly.
        if _is_streaming(camera_id):
            cached = _get_cached_frame(camera_id)
            if cached is not None:
                image = self._resize_to_max_width(cached, max_width)
                ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), max(30, min(quality, 95))])
                if ok:
                    return encoded.tobytes()

        lock = _get_camera_lock(camera_id)
        # Try to acquire without blocking so detection never freezes the preview.
        acquired = lock.acquire(timeout=0.08)  # 80 ms non-blocking try
        if not acquired:
            # Camera busy (detection running) — serve cached frame if available.
            cached = _get_cached_frame(camera_id)
            if cached is not None:
                logger.debug("preview cache hit for %s", camera_id)
                image = self._resize_to_max_width(cached, max_width)
                ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), max(30, min(quality, 95))])
                if ok:
                    return encoded.tobytes()
            # No cache yet — wait for the lock (first request ever).
            lock.acquire()
            acquired = True
        try:
            with self._create_camera_source(camera_id) as camera:
                frame = camera.capture_frame()
            _cache_frame(camera_id, frame.image)
            image = self._resize_to_max_width(frame.image, max_width)
            ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), max(30, min(quality, 95))])
            if not ok:
                raise RuntimeError("無法編碼鏡頭畫面")
            return encoded.tobytes()
        finally:
            lock.release()

    def stream_mjpeg(
        self,
        camera_id: str,
        max_width: int | None = None,
        quality: int = 75,
    ):
        """Yield MJPEG multipart frame bytes (for StreamingResponse).

        Opens the physical camera exactly once and captures in a tight loop —
        the same behaviour as `python -m backend.main --mode preview`.  The
        frame cache is updated on every capture so that concurrent detection
        calls can use a cached frame without waiting for the camera lock.

        If a second client hits this endpoint while the camera is already
        streaming, frames are served from the cache at up to ~30 fps without
        reopening the camera.
        """
        import queue as _queue

        # ── Secondary client: camera already streaming → serve from cache ──
        if _is_streaming(camera_id):
            import time as _t
            while True:
                cached = _get_cached_frame(camera_id)
                if cached is not None:
                    image = self._resize_to_max_width(cached, max_width)
                    ok, enc = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), max(30, min(quality, 95))])
                    if ok:
                        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + enc.tobytes() + b"\r\n"
                _t.sleep(0.033)  # ~30 fps
            return

        # ── Primary client: open camera, stream until disconnect ────────────
        frame_q: _queue.Queue[bytes | None] = _queue.Queue(maxsize=4)
        stop_event = threading.Event()

        with _ACTIVE_STREAMS_MU:
            _ACTIVE_STREAMS[camera_id] = True

        def _capture_loop() -> None:
            lock = _get_camera_lock(camera_id)
            lock.acquire()
            try:
                with self._create_camera_source(camera_id) as cam:
                    while not stop_event.is_set():
                        try:
                            frame = cam.capture_frame()
                        except Exception as exc:
                            logger.warning("mjpeg capture error for %s: %s", camera_id, exc)
                            break
                        _cache_frame(camera_id, frame.image)
                        image = self._resize_to_max_width(frame.image, max_width)
                        ok, enc = cv2.imencode(
                            ".jpg", image,
                            [int(cv2.IMWRITE_JPEG_QUALITY), max(30, min(quality, 95))],
                        )
                        if ok:
                            try:
                                frame_q.put_nowait(enc.tobytes())
                            except _queue.Full:
                                pass  # drop frame; client is slow
            except Exception as exc:
                logger.error("Failed to initialize or run camera %s: %s", camera_id, exc)
            finally:
                lock.release()
                with _ACTIVE_STREAMS_MU:
                    _ACTIVE_STREAMS.pop(camera_id, None)
                frame_q.put(None)  # sentinel — signal generator to stop

        thread = threading.Thread(target=_capture_loop, daemon=True, name=f"mjpeg-{camera_id}")
        thread.start()

        try:
            while True:
                try:
                    jpg = frame_q.get(timeout=5.0)
                except _queue.Empty:
                    break
                if jpg is None:
                    break
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
        finally:
            stop_event.set()
            thread.join(timeout=5.0)

    def capture_and_detect(self, camera_id: str, model_type: str = "opencv") -> DetectionRunResult:
        # When MJPEG stream owns the camera, use the continuously-updated cache
        # instead of trying to acquire the lock (which would block forever).
        if _is_streaming(camera_id):
            cached = _get_cached_frame(camera_id)
            if cached is not None:
                return self._detection_service.run_detection_on_image(
                    image=cached,
                    filename=f"{camera_id}.jpg",
                    model_type=model_type,
                    image_source="camera",
                    camera_id=camera_id,
                )

        with _get_camera_lock(camera_id):
            with self._create_camera_source(camera_id) as camera:
                frame = camera.capture_frame()
            _cache_frame(camera_id, frame.image)

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
        # Always detect on FULL resolution for maximum DataMatrix accuracy.
        # Bboxes are returned in full-res coordinates; sourceImage reports
        # the actual dimensions so the frontend overlay scales correctly.
        if _is_streaming(camera_id):
            cached = _get_cached_frame(camera_id)
            if cached is not None:
                return self._detection_service.preview_detection_on_image(
                    image=cached,
                    filename=f"{camera_id}.jpg",
                    model_type=model_type,
                    image_source="camera-preview",
                    camera_id=camera_id,
                    save_preview_image=False,
                )

        with _get_camera_lock(camera_id):
            with self._create_camera_source(camera_id) as camera:
                frame = camera.capture_frame()
            _cache_frame(camera_id, frame.image)

        return self._detection_service.preview_detection_on_image(
            image=frame.image,
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
        allow_opencv_fallback = bool(cfg.get("allow_opencv_fallback", False))

        try:
            available, status = self._probe_by_type(source_type, camera_num, allow_opencv_fallback=allow_opencv_fallback)
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

    def _probe_by_type(
        self,
        source_type: str,
        camera_num: int,
        *,
        allow_opencv_fallback: bool = False,
    ) -> tuple[bool, str | None]:
        if source_type == "arducam":
            # Prefer Picamera2 whenever available, regardless of platform
            # detection heuristics. This avoids misrouting CSI cameras to V4L2.
            if _is_picamera2_available():
                picam_ok, picam_status = self._probe_picamera(camera_num)
                if picam_ok:
                    return True, picam_status

                if allow_opencv_fallback or not _is_raspberry_pi():
                    opencv_ok, opencv_status = self._probe_opencv(camera_num)
                    if opencv_ok:
                        return True, f"opencv fallback: {opencv_status}"
                    return False, f"picamera={picam_status}; opencv={opencv_status}"

                return False, f"picamera={picam_status}"

            if _is_raspberry_pi():
                if allow_opencv_fallback:
                    opencv_ok, opencv_status = self._probe_opencv(camera_num)
                    if opencv_ok:
                        return True, f"opencv fallback: {opencv_status}"
                    return False, f"opencv={opencv_status}"
                return False, _rpi_picamera_dependency_message()

            return self._probe_opencv(camera_num)

        if source_type == "opencv" or source_type == "arducam":
            return self._probe_opencv(camera_num)
        return self._probe_picamera(camera_num)

    def _probe_picamera(self, camera_num: int) -> tuple[bool, str | None]:
        """Probe a PiCamera by first checking global_camera_info, then opening."""
        # Step 1: non-invasive check — picamera2 can list cameras without opening them
        available_cams = PiCameraSource.available_cameras()
        logger.info("PiCamera probe: available_cameras() = %s", available_cams)

        if available_cams:
            resolved_num, remapped, available_nums = self._resolve_picamera_num(camera_num, available_cams)
            if resolved_num not in available_nums:
                msg = f"鏡頭 {camera_num} 未找到 (可用索引: {available_nums})"
                logger.warning("PiCamera probe: %s", msg)
                return False, msg
            # Camera index exists — return info without fully opening it
            info = available_cams[available_nums.index(resolved_num)]
            model = info.get("Model", "unknown")
            status = f"picam{resolved_num} ({model})"
            if remapped:
                status = f"{status}, configured={camera_num}"
                logger.warning(
                    "PiCamera probe: remapped configured camera_num=%d to actual Num=%d (available=%s)",
                    camera_num,
                    resolved_num,
                    available_nums,
                )
            logger.info("PiCamera probe: camera %d found — %s", resolved_num, status)
            return True, status

        # Step 2: fallback — try opening (slower, ensures picamera2 works)
        resolved_num, remapped, available_nums = self._resolve_picamera_num(camera_num, available_cams)
        if remapped:
            logger.warning(
                "PiCamera probe fallback: remapped configured camera_num=%d to actual Num=%d (available=%s)",
                camera_num,
                resolved_num,
                available_nums,
            )
        logger.warning(
            "PiCamera probe: global_camera_info returned empty, trying to open camera %d directly",
            resolved_num,
        )
        source = PiCameraSource(camera_num=resolved_num)
        try:
            source.open()
            frame = source.capture_frame()
            status = f"{frame.resolution[0]}x{frame.resolution[1]}"
            if remapped:
                status = f"{status}, configured={camera_num}, actual={resolved_num}"
            return True, status
        except Exception as exc:
            logger.warning("PiCamera probe failed for camera %d: %s", resolved_num, exc)
            return False, str(exc)
        finally:
            # Always release resources, even if capture_frame() raised
            try:
                source.close()
            except Exception:
                pass

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
        allow_opencv_fallback = bool(cfg.get("allow_opencv_fallback", False))

        if source_type == "arducam":
            # Prefer Picamera2 for Arducam when available. This covers Raspberry Pi
            # CSI workflows even if platform model detection is imperfect.
            if _is_picamera2_available():
                resolved_num, remapped, available_nums = self._resolve_picamera_num(camera_num)
                if remapped:
                    logger.warning(
                        "Camera %s remapped configured camera_num=%d to actual Num=%d (available=%s)",
                        camera_id,
                        camera_num,
                        resolved_num,
                        available_nums,
                    )

                if not allow_opencv_fallback:
                    return PiCameraSource(
                        camera_num=resolved_num,
                        width=width,
                        height=height,
                        camera_id=camera_id,
                    )

                return _FallbackCameraSource(
                    camera_id=camera_id,
                    primary_name="picamera2",
                    fallback_name="opencv",
                    primary_factory=lambda: PiCameraSource(
                        camera_num=resolved_num,
                        width=width,
                        height=height,
                        camera_id=camera_id,
                    ),
                    fallback_factory=lambda: OpenCVCameraSource(
                        camera_num=camera_num,
                        width=width,
                        height=height,
                        camera_id=camera_id,
                    ),
                )

            if _is_raspberry_pi() and not allow_opencv_fallback:
                raise RuntimeError(_rpi_picamera_dependency_message())

            return OpenCVCameraSource(
                camera_num=camera_num,
                width=width,
                height=height,
                camera_id=camera_id,
            )

        if source_type == "opencv" or source_type == "arducam":
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