from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class ImageSize(BaseModel):
    width: int
    height: int


class ModelInfo(BaseModel):
    id: str
    modelName: str
    modelType: str
    modelVersion: str
    framework: str
    modelPath: str
    isActive: bool
    remark: str | None = None
    createdAt: str
    updatedAt: str


class DetectionObject(BaseModel):
    id: str
    rid: str
    bid: str
    bbox: BoundingBox
    barcodeValue: str | None = None
    barcodeType: str | None = None
    ocrText: str | None = None
    confidenceScore: float = Field(default=0.0, ge=0.0, le=1.0)
    modelId: str
    model: ModelInfo
    imagePath: str | None = None
    remark: str | None = None
    createdAt: str
    updatedAt: str


class DetectionBatch(BaseModel):
    rid: str
    objectCount: int
    barcodeSuccessCount: int
    ocrSuccessCount: int
    model: ModelInfo
    createdAt: str
    objects: list[DetectionObject]


class DetectionResponse(BaseModel):
    rid: str
    imagePath: str | None = None
    objects: list[DetectionObject]
    sourceImage: ImageSize | None = None


class CameraInfo(BaseModel):
    id: str
    label: str
    sourceType: str
    cameraNum: int
    width: int
    height: int
    available: bool
    status: str | None = None


class CameraListResponse(BaseModel):
    items: list[CameraInfo]


class DetectionBatchList(BaseModel):
    items: list[DetectionBatch]


class ModelListResponse(BaseModel):
    items: list[ModelInfo]


class TrendPoint(BaseModel):
    label: str
    rounds: int
    objects: int


class StatsSummary(BaseModel):
    totalRounds: int
    totalObjects: int
    barcodeSuccessRate: float
    ocrSuccessRate: float
    activeModelCount: int
    recentRounds: list[DetectionBatch]
    trends: list[TrendPoint]


class UpdateRemarkRequest(BaseModel):
    remark: str = Field(min_length=0, max_length=1000)
