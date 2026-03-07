import {
  type DetectionBatch,
  type DetectionObject,
  type DetectionResponse,
  type ModelInfo,
  type StatsSummary,
} from "@/types";

const now = new Date();

export const models: ModelInfo[] = [
  {
    id: "mdl-opencv-001",
    modelName: "OpenCV Contour Detector",
    modelType: "opencv",
    modelVersion: "0.9.0",
    framework: "opencv",
    modelPath: "builtin://opencv/contour-detector",
    isActive: true,
    remark: "MVP 預設偵測模型",
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
  },
  {
    id: "mdl-yolo-001",
    modelName: "YOLO Candidate Detector",
    modelType: "yolo",
    modelVersion: "0.1.0",
    framework: "ultralytics",
    modelPath: "models/trained/yolo_candidate.pt",
    isActive: false,
    remark: "預留後續切換",
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
  },
  {
    id: "mdl-ocr-001",
    modelName: "OCR Reader",
    modelType: "ocr",
    modelVersion: "0.3.0",
    framework: "tesseract",
    modelPath: "builtin://ocr/tesseract",
    isActive: true,
    remark: "文字辨識模組",
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
  },
];

function makeObject(index: number, rid: string): DetectionObject {
  const detector = models[0];
  return {
    id: `${rid}-obj-${index}`,
    rid,
    bid: `B-${String(index).padStart(3, "0")}`,
    bbox: {
      x1: 40 + index * 36,
      y1: 50 + index * 18,
      x2: 180 + index * 42,
      y2: 180 + index * 22,
    },
    barcodeValue: index % 2 === 0 ? `DMX-24030${index}` : null,
    barcodeType: index % 2 === 0 ? "DataMatrix" : null,
    ocrText: index % 3 === 0 ? `BOX-${index} / LOT-202603` : `Label ${index}`,
    confidenceScore: Number((0.82 + index * 0.03).toFixed(2)),
    modelId: detector.id,
    model: detector,
    imagePath: `/mock/result-${rid}.png`,
    remark: index % 2 === 0 ? "barcode 辨識成功" : "待人工確認",
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
  };
}

export const batches: DetectionBatch[] = [
  {
    rid: "RID-20260307-001",
    objectCount: 4,
    barcodeSuccessCount: 2,
    ocrSuccessCount: 4,
    model: models[0],
    createdAt: new Date(now.getTime() - 1000 * 60 * 12).toISOString(),
    objects: [1, 2, 3, 4].map((n) => makeObject(n, "RID-20260307-001")),
  },
  {
    rid: "RID-20260307-002",
    objectCount: 6,
    barcodeSuccessCount: 4,
    ocrSuccessCount: 6,
    model: models[0],
    createdAt: new Date(now.getTime() - 1000 * 60 * 45).toISOString(),
    objects: [1, 2, 3, 4, 5, 6].map((n) => makeObject(n, "RID-20260307-002")),
  },
  {
    rid: "RID-20260306-019",
    objectCount: 5,
    barcodeSuccessCount: 3,
    ocrSuccessCount: 5,
    model: models[0],
    createdAt: new Date(now.getTime() - 1000 * 60 * 60 * 5).toISOString(),
    objects: [1, 2, 3, 4, 5].map((n) => makeObject(n, "RID-20260306-019")),
  },
];

export const statsSummary: StatsSummary = {
  totalRounds: 138,
  totalObjects: 764,
  barcodeSuccessRate: 87.4,
  ocrSuccessRate: 94.2,
  activeModelCount: models.filter((model) => model.isActive).length,
  recentRounds: batches,
  trends: [
    { label: "Mon", rounds: 15, objects: 82 },
    { label: "Tue", rounds: 18, objects: 97 },
    { label: "Wed", rounds: 22, objects: 124 },
    { label: "Thu", rounds: 19, objects: 110 },
    { label: "Fri", rounds: 24, objects: 140 },
    { label: "Sat", rounds: 10, objects: 54 },
    { label: "Sun", rounds: 8, objects: 39 },
  ],
};

export function getBatchByRid(rid: string) {
  return batches.find((batch) => batch.rid === rid) ?? null;
}

export function getObjectByBid(bid: string) {
  return batches.flatMap((batch) => batch.objects).find((item) => item.bid === bid) ?? null;
}

export function buildMockDetectionResponse(): DetectionResponse {
  const rid = `RID-${Date.now()}`;
  const objects = [1, 2, 3, 4].map((index) => makeObject(index, rid));
  return { rid, objects };
}
