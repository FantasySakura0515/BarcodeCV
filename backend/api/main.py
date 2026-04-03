from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    CameraInfo,
    CameraListResponse,
    CreateCustomerRequest,
    CreateDeviceRequest,
    CustomerInfo,
    CustomerListResponse,
    DetectionBatch,
    DetectionBatchList,
    DetectionObject,
    DetectionResponse,
    DeviceInfo,
    DeviceListResponse,
    ModelListResponse,
    SettingInfo,
    SettingListResponse,
    StatsSummary,
    UpsertSettingRequest,
    UpdateRemarkRequest,
)
from ..database.business_repository import BusinessRepository
from ..camera.camarray_guard import run_camarray_startup_check
from ..database.db_manager import DatabaseManager
from ..services.detection_records_service import DetectionRecordsService
from ..services.detection_service import DetectionService
from ..services.camera_service import CameraService
from ..services.model_service import ModelService
from ..services.stats_service import StatsService
from ..camera.picamera_source import PiCameraSource
from ..utils.config_loader import load_config
from ..utils.logger import setup_logger


def _is_supported_upload(file: UploadFile) -> bool:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type in {"image/jpeg", "image/png", "image/jpg", "application/pdf"}:
        return True

    file_name = (file.filename or "").lower()
    return (
        file_name.endswith(".jpg")
        or file_name.endswith(".jpeg")
        or file_name.endswith(".png")
        or file_name.endswith(".pdf")
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    setup_logger(
        log_level=config.get("system", {}).get("log_level", "INFO"),
        log_file=config.get("system", {}).get("log_file"),
    )

    db_manager = DatabaseManager(
        db_path=config["database"]["path"],
        wal_mode=config["database"].get("wal_mode", True),
    )
    db_manager.connect()
    db_manager.initialize_schema()
    BusinessRepository(db_manager.get_connection()).ensure_seed_data()

    model_service = ModelService(db_manager.get_connection())
    model_service.ensure_seed_models()
    detection_service = DetectionService(db_manager.get_connection(), config)
    detection_records_service = DetectionRecordsService(db_manager.get_connection())
    camera_service = CameraService(config, detection_service)
    stats_service = StatsService(db_manager.get_connection(), config)
    camarray_report = run_camarray_startup_check(config)

    image_dir = Path(config.get("system", {}).get("image_output_dir", "./output/images"))
    image_dir.mkdir(parents=True, exist_ok=True)

    app.state.config = config
    app.state.db_manager = db_manager
    app.state.model_service = model_service
    app.state.detection_service = detection_service
    app.state.detection_records_service = detection_records_service
    app.state.camera_service = camera_service
    app.state.stats_service = stats_service
    app.state.camarray_report = camarray_report
    yield
    db_manager.close()


app = FastAPI(
    title="BarcodeCV Backend",
    version="0.1.0",
    lifespan=lifespan,
    description="BarcodeCV FastAPI backend for DataMatrix detection, annotation, and decoding.",
)

_config = load_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_config.get("api", {}).get("cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = Path(_config.get("system", {}).get("image_output_dir", "./output/images"))
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=str(_static_dir)), name="images")


def get_detection_service() -> DetectionService:
    return app.state.detection_service


def get_model_service() -> ModelService:
    return app.state.model_service


def get_detection_records_service() -> DetectionRecordsService:
    return app.state.detection_records_service


def get_camera_service() -> CameraService:
    return app.state.camera_service


def get_stats_service() -> StatsService:
    return app.state.stats_service


def get_business_repository() -> BusinessRepository:
    return BusinessRepository(app.state.db_manager.get_connection())


def _to_customer_info(row) -> CustomerInfo:
    return CustomerInfo(
        id=str(row["id"]),
        name=row["name"],
        code=row["code"],
        description=row["description"],
        email=row["email"],
        phone=row["phone"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _to_device_info(row) -> DeviceInfo:
    return DeviceInfo(
        id=str(row["id"]),
        name=row["name"],
        code=row["code"],
        type=row["type"],
        location=row["location"],
        isActive=bool(row["is_active"]),
        isDeletable=bool(row["is_deletable"]),
        lastSeenAt=row["last_seen_at"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _to_setting_info(row) -> SettingInfo:
    return SettingInfo(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        settingKey=row["setting_key"],
        settingValue=row["setting_value"],
        isDeletable=bool(row["is_deletable"]),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _to_detection_response(result) -> DetectionResponse:
    return DetectionResponse(
        rid=result.rid,
        imagePath=result.image_path,
        objects=result.objects,
        sourceImage=result.source_image,
        objectCount=result.object_count,
        datamatrixSuccessCount=result.datamatrix_success_count,
        requiresReposition=result.requires_reposition,
        placementHint=result.placement_hint,
    )


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/customers", response_model=CustomerListResponse)
def list_customers() -> CustomerListResponse:
    rows = get_business_repository().list_customers()
    return CustomerListResponse(items=[_to_customer_info(row) for row in rows])


@app.post("/api/customers", response_model=CustomerInfo)
def create_customer(payload: CreateCustomerRequest) -> CustomerInfo:
    try:
        row = get_business_repository().create_customer(
            name=payload.name,
            code=payload.code,
            description=payload.description,
            email=payload.email,
            phone=payload.phone,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to create customer: {exc}") from exc
    return _to_customer_info(row)


@app.get("/api/devices", response_model=DeviceListResponse)
def list_devices() -> DeviceListResponse:
    rows = get_business_repository().list_devices()
    return DeviceListResponse(items=[_to_device_info(row) for row in rows])


@app.post("/api/devices", response_model=DeviceInfo)
def create_device(payload: CreateDeviceRequest) -> DeviceInfo:
    try:
        row = get_business_repository().create_device(
            name=payload.name,
            code=payload.code,
            device_type=payload.type,
            location=payload.location,
            is_active=payload.isActive,
            is_deletable=payload.isDeletable,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to create device: {exc}") from exc
    return _to_device_info(row)


@app.get("/api/settings", response_model=SettingListResponse)
def list_settings() -> SettingListResponse:
    rows = get_business_repository().list_settings()
    return SettingListResponse(items=[_to_setting_info(row) for row in rows])


@app.put("/api/settings/{setting_key}", response_model=SettingInfo)
def upsert_setting(setting_key: str, payload: UpsertSettingRequest) -> SettingInfo:
    row = get_business_repository().upsert_setting(
        name=payload.name,
        setting_key=setting_key,
        setting_value=payload.settingValue,
        description=payload.description,
        is_deletable=payload.isDeletable,
    )
    return _to_setting_info(row)


@app.get("/api/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    items = get_model_service().list_models()
    return ModelListResponse(items=items)


@app.post("/api/detections", response_model=DetectionResponse)
async def create_detection(
    file: UploadFile = File(...),
    modelType: str = Form(default="opencv"),
) -> DetectionResponse:
    if not _is_supported_upload(file):
        raise HTTPException(status_code=400, detail="Only jpg / jpeg / png / pdf are supported.")

    content = await file.read()
    try:
        detection_service = get_detection_service()
        image = detection_service.decode_upload_bytes(
            file_bytes=content,
            filename=file.filename or "upload",
            content_type=file.content_type,
        )
        result = detection_service.run_detection_on_image(
            image=image,
            filename=file.filename or "upload.png",
            model_type=modelType,
            image_source="upload",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Detection request failed: {exc}") from exc

    return _to_detection_response(result)


@app.post("/api/live-preview-detection", response_model=DetectionResponse)
@app.post("/api/detections/preview", response_model=DetectionResponse)
async def create_preview_detection(
    file: UploadFile = File(...),
    modelType: str = Form(default="opencv"),
) -> DetectionResponse:
    if not _is_supported_upload(file):
        raise HTTPException(status_code=400, detail="Only jpg / jpeg / png / pdf are supported.")

    content = await file.read()
    try:
        detection_service = get_detection_service()
        image = detection_service.decode_upload_bytes(
            file_bytes=content,
            filename=file.filename or "preview",
            content_type=file.content_type,
        )
        result = detection_service.preview_detection_on_image(
            image=image,
            filename=file.filename or "preview.png",
            model_type=modelType,
            image_source="preview-upload",
            save_preview_image=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Preview detection failed: {exc}") from exc

    return _to_detection_response(result)


@app.get("/api/cameras", response_model=CameraListResponse)
def list_cameras() -> CameraListResponse:
    items = [
        CameraInfo(
            id=item.id,
            label=item.label,
            sourceType=item.source_type,
            cameraNum=item.camera_num,
            width=item.width,
            height=item.height,
            available=item.available,
            status=item.status,
        )
        for item in get_camera_service().list_cameras()
    ]
    return CameraListResponse(items=items)


@app.get("/api/cameras/debug")
def debug_cameras() -> dict:
    """Diagnostic endpoint: returns detailed camera detection info.

    Useful on Raspberry Pi to see why cameras appear as unavailable.
    Call via browser or curl:  GET /api/cameras/debug
    """
    diagnostics = PiCameraSource.diagnose()
    startup_report = getattr(app.state, "camarray_report", None)
    suggested_fixes: list[str] = []
    picamera_num_mapping_preview: list[dict] = []

    if diagnostics.get("picamera2_import_error"):
        suggested_fixes.append(
            "sudo apt update && sudo apt install -y python3-picamera2 python3-libcamera libcamera-apps v4l-utils"
        )
        suggested_fixes.append("bash scripts/fix_venv_pi.sh")

    if diagnostics.get("global_camera_info_error") and not diagnostics.get("global_camera_info"):
        suggested_fixes.append("libcamera-hello --list-cameras")

    if isinstance(diagnostics.get("global_camera_info"), list) and not diagnostics.get("global_camera_info"):
        suggested_fixes.append("libcamera-hello --list-cameras  # if empty, check CSI ribbon cable and /boot/firmware/config.txt")
        suggested_fixes.append("sudo raspi-config  # Interface Options -> Camera; reboot and test again")
        suggested_fixes.append(
            "If using USB/UVC Arducam, set cameras.main.allow_opencv_fallback to true in config/default.yaml"
        )
        suggested_fixes.append("B0402 dual mode: sudo i2cset -y 10 0x24 0x24 0x01")

    global_camera_info = diagnostics.get("global_camera_info")
    if isinstance(global_camera_info, list):
        available_nums: list[int] = []
        for i, info in enumerate(global_camera_info):
            if not isinstance(info, dict):
                continue
            raw_num = info.get("Num", i)
            try:
                available_nums.append(int(raw_num))
            except (TypeError, ValueError):
                available_nums.append(i)

        configured = getattr(app.state, "config", {}).get("cameras", {})
        if isinstance(configured, dict) and available_nums:
            for role, cfg in configured.items():
                if not isinstance(cfg, dict):
                    continue
                try:
                    configured_num = int(cfg.get("camera_num", 0))
                except (TypeError, ValueError):
                    configured_num = 0
                resolved_num = configured_num
                remapped = False
                if configured_num not in available_nums and 0 <= configured_num < len(available_nums):
                    resolved_num = available_nums[configured_num]
                    remapped = True

                picamera_num_mapping_preview.append(
                    {
                        "camera_id": role,
                        "configured_num": configured_num,
                        "resolved_num": resolved_num,
                        "remapped": remapped,
                        "available_nums": available_nums,
                    }
                )

    return {
        "configured_cameras": list(getattr(app.state, "config", {}).get("cameras", {}).keys()),
        "probe_results": [
            {
                "id": item.id,
                "camera_num": item.camera_num,
                "source_type": item.source_type,
                "available": item.available,
                "status": item.status,
            }
            for item in get_camera_service().list_cameras()
        ],
        "system_diagnostics": diagnostics,
        "camarray_startup_check": startup_report,
        "picamera_num_mapping_preview": picamera_num_mapping_preview,
        "suggested_fixes": suggested_fixes,
    }


@app.get("/api/cameras/{camera_id}/preview")
def get_camera_preview(camera_id: str, maxWidth: int | None = 640, quality: int = 70) -> Response:
    try:
        image_bytes = get_camera_service().capture_preview(camera_id, max_width=maxWidth, quality=quality)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Camera preview failed: {exc}") from exc

    return Response(content=image_bytes, media_type="image/jpeg")


@app.get("/api/cameras/{camera_id}/stream")
def stream_camera_mjpeg(camera_id: str, maxWidth: int | None = None, quality: int = 75) -> StreamingResponse:
    """MJPEG live stream endpoint.

    Keeps the physical camera open and pushes frames continuously as
    multipart/x-mixed-replace. Browsers can consume this directly via:
        <img src="/api/cameras/{id}/stream">

    Frame rate is limited only by camera capture speed and JPEG encoding.
    Detection calls run concurrently by reading the frame cache.
    """
    try:
        def _gen():
            yield from get_camera_service().stream_mjpeg(camera_id, max_width=maxWidth, quality=quality)

        return StreamingResponse(
            _gen(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/cameras/{camera_id}/capture-detection", response_model=DetectionResponse)
def capture_camera_detection(
    camera_id: str,
    modelType: str = Form(default="opencv"),
) -> DetectionResponse:
    try:
        result = get_camera_service().capture_and_detect(camera_id, modelType)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Camera capture detection failed: {exc}") from exc

    return _to_detection_response(result)


@app.get("/api/cameras/{camera_id}/live-detection", response_model=DetectionResponse)
def live_camera_detection(camera_id: str, modelType: str = "opencv", maxWidth: int | None = 640) -> DetectionResponse:
    try:
        result = get_camera_service().preview_and_detect(camera_id, modelType, max_width=maxWidth)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Live camera detection failed: {exc}") from exc

    return _to_detection_response(result)


@app.get("/api/detections", response_model=DetectionBatchList)
def list_detections() -> DetectionBatchList:
    items = get_detection_records_service().list_batches(limit=50)
    return DetectionBatchList(items=items)


@app.get("/api/detections/{rid}", response_model=DetectionBatch)
def get_detection_batch(rid: str) -> DetectionBatch:
    result = get_detection_records_service().get_batch(rid)
    if result is None:
        raise HTTPException(status_code=404, detail="Detection batch not found.")
    return DetectionBatch(**result)


@app.get("/api/objects/{bid}", response_model=DetectionObject)
def get_object(bid: str) -> DetectionObject:
    result = get_detection_records_service().get_object(bid)
    if result is None:
        raise HTTPException(status_code=404, detail="Detection object not found.")
    return DetectionObject(**result)


@app.patch("/api/objects/{bid}", response_model=DetectionObject)
def update_object(bid: str, payload: UpdateRemarkRequest) -> DetectionObject:
    result = get_detection_records_service().update_object_remark(bid, payload.remark)
    if result is None:
        raise HTTPException(status_code=404, detail="Detection object not found.")
    return DetectionObject(**result)


@app.get("/api/stats/summary", response_model=StatsSummary)
def get_stats_summary() -> StatsSummary:
    return StatsSummary(**get_stats_service().get_summary())


