from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .schemas import (
    CameraInfo,
    CameraListResponse,
    DetectionBatch,
    DetectionBatchList,
    DetectionObject,
    DetectionResponse,
    ModelListResponse,
    StatsSummary,
    UpdateRemarkRequest,
)
from ..database.db_manager import DatabaseManager
from ..services.detection_service import DetectionService
from ..services.camera_service import CameraService
from ..services.model_service import ModelService
from ..services.stats_service import StatsService
from ..camera.picamera_source import PiCameraSource
from ..utils.config_loader import load_config
from ..utils.logger import setup_logger


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

    model_service = ModelService(db_manager.get_connection())
    model_service.ensure_seed_models()

    image_dir = Path(config.get("system", {}).get("image_output_dir", "./output/images"))
    image_dir.mkdir(parents=True, exist_ok=True)

    app.state.config = config
    app.state.db_manager = db_manager
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
    return DetectionService(app.state.db_manager.get_connection(), app.state.config)


def get_model_service() -> ModelService:
    return ModelService(app.state.db_manager.get_connection())


def get_camera_service() -> CameraService:
    return CameraService(getattr(app.state, "config"), get_detection_service())


def get_stats_service() -> StatsService:
    return StatsService(app.state.db_manager.get_connection(), app.state.config)


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    items = get_model_service().list_models()
    return ModelListResponse(items=items)


@app.post("/api/detections", response_model=DetectionResponse)
async def create_detection(
    file: UploadFile = File(...),
    modelType: str = Form(default="opencv"),
) -> DetectionResponse:
    if file.content_type not in {"image/jpeg", "image/png", "image/jpg"}:
        raise HTTPException(status_code=400, detail="僅支援 jpg / jpeg / png")

    content = await file.read()
    try:
        result = get_detection_service().run_detection(
            file_bytes=content,
            filename=file.filename or "upload.png",
            model_type=modelType,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"檢測流程失敗: {exc}") from exc

    return DetectionResponse(
        rid=result.rid,
        imagePath=result.image_path,
        objects=result.objects,
        sourceImage=result.source_image,
    )


@app.post("/api/live-preview-detection", response_model=DetectionResponse)
@app.post("/api/detections/preview", response_model=DetectionResponse)
async def create_preview_detection(
    file: UploadFile = File(...),
    modelType: str = Form(default="opencv"),
) -> DetectionResponse:
    if file.content_type not in {"image/jpeg", "image/png", "image/jpg"}:
        raise HTTPException(status_code=400, detail="僅支援 jpg / jpeg / png")

    content = await file.read()
    try:
        image = get_detection_service()._decode_image(content)
        result = get_detection_service().preview_detection_on_image(
            image=image,
            filename=file.filename or "preview.png",
            model_type=modelType,
            image_source="preview-upload",
            save_preview_image=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"即時辨識流程失敗: {exc}") from exc

    return DetectionResponse(
        rid=result.rid,
        imagePath=result.image_path,
        objects=result.objects,
        sourceImage=result.source_image,
    )


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
        "system_diagnostics": PiCameraSource.diagnose(),
    }


@app.get("/api/cameras/{camera_id}/preview")
def get_camera_preview(camera_id: str, maxWidth: int | None = 640, quality: int = 70) -> Response:
    try:
        image_bytes = get_camera_service().capture_preview(camera_id, max_width=maxWidth, quality=quality)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"無法取得鏡頭畫面: {exc}") from exc

    return Response(content=image_bytes, media_type="image/jpeg")


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
        raise HTTPException(status_code=503, detail=f"鏡頭擷取失敗: {exc}") from exc

    return DetectionResponse(
        rid=result.rid,
        imagePath=result.image_path,
        objects=result.objects,
        sourceImage=result.source_image,
    )


@app.get("/api/cameras/{camera_id}/live-detection", response_model=DetectionResponse)
def live_camera_detection(camera_id: str, modelType: str = "opencv", maxWidth: int | None = 640) -> DetectionResponse:
    try:
        result = get_camera_service().preview_and_detect(camera_id, modelType, max_width=maxWidth)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"即時辨識失敗: {exc}") from exc

    return DetectionResponse(
        rid=result.rid,
        imagePath=result.image_path,
        objects=result.objects,
        sourceImage=result.source_image,
    )


@app.get("/api/detections", response_model=DetectionBatchList)
def list_detections() -> DetectionBatchList:
    items = get_detection_service().list_batches(limit=50)
    return DetectionBatchList(items=items)


@app.get("/api/detections/{rid}", response_model=DetectionBatch)
def get_detection_batch(rid: str) -> DetectionBatch:
    result = get_detection_service().get_batch(rid)
    if result is None:
        raise HTTPException(status_code=404, detail="找不到指定批次")
    return DetectionBatch(**result)


@app.get("/api/objects/{bid}", response_model=DetectionObject)
def get_object(bid: str) -> DetectionObject:
    result = get_detection_service().get_object(bid)
    if result is None:
        raise HTTPException(status_code=404, detail="找不到指定物件")
    return DetectionObject(**result)


@app.patch("/api/objects/{bid}", response_model=DetectionObject)
def update_object(bid: str, payload: UpdateRemarkRequest) -> DetectionObject:
    result = get_detection_service().update_object_remark(bid, payload.remark)
    if result is None:
        raise HTTPException(status_code=404, detail="找不到指定物件")
    return DetectionObject(**result)


@app.get("/api/stats/summary", response_model=StatsSummary)
def get_stats_summary() -> StatsSummary:
    return StatsSummary(**get_stats_service().get_summary())
