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


class CustomerInfo(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    email: str | None = None
    phone: str | None = None
    createdAt: str
    updatedAt: str


class CustomerRef(BaseModel):
    id: str
    name: str
    code: str


class DeviceInfo(BaseModel):
    id: str
    name: str
    code: str
    type: str
    location: str | None = None
    isActive: bool
    isDeletable: bool
    lastSeenAt: str | None = None
    createdAt: str
    updatedAt: str


class SettingInfo(BaseModel):
    id: str
    name: str
    description: str | None = None
    settingKey: str
    settingValue: str
    isDeletable: bool
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
    name: str | None = None
    description: str | None = None
    customer: CustomerRef | None = None
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
    objectCount: int
    datamatrixSuccessCount: int
    requiresReposition: bool
    placementHint: str


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


class CustomerListResponse(BaseModel):
    items: list[CustomerInfo]


class DeviceListResponse(BaseModel):
    items: list[DeviceInfo]


class SettingListResponse(BaseModel):
    items: list[SettingInfo]


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


class CreateCustomerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=100)


class CreateDeviceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    isActive: bool = True
    isDeletable: bool = True


class UpsertSettingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    settingKey: str = Field(min_length=1, max_length=200)
    settingValue: str = Field(min_length=0, max_length=4000)
    description: str | None = Field(default=None, max_length=1000)
    isDeletable: bool = True
