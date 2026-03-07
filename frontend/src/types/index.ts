export type ModelType = "opencv" | "yolo" | "ocr";

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface ImageSize {
  width: number;
  height: number;
}

export interface ModelInfo {
  id: string;
  modelName: string;
  modelType: ModelType;
  modelVersion: string;
  framework: string;
  modelPath: string;
  isActive: boolean;
  remark?: string;
  createdAt: string;
  updatedAt: string;
}

export interface DetectionObject {
  id: string;
  rid: string;
  bid: string;
  bbox: BoundingBox;
  barcodeValue: string | null;
  barcodeType: string | null;
  ocrText: string | null;
  confidenceScore: number;
  modelId: string;
  model: ModelInfo;
  imagePath?: string;
  remark?: string;
  createdAt: string;
  updatedAt: string;
}

export interface DetectionBatch {
  rid: string;
  objectCount: number;
  barcodeSuccessCount: number;
  ocrSuccessCount: number;
  model: ModelInfo;
  createdAt: string;
  objects: DetectionObject[];
}

export interface StatsSummary {
  totalRounds: number;
  totalObjects: number;
  barcodeSuccessRate: number;
  ocrSuccessRate: number;
  activeModelCount: number;
  recentRounds: DetectionBatch[];
  trends: Array<{
    label: string;
    rounds: number;
    objects: number;
  }>;
}

export interface DetectionResponse {
  rid: string;
  imagePath?: string | null;
  objects: DetectionObject[];
  sourceImage?: ImageSize | null;
}

export interface CameraInfo {
  id: string;
  label: string;
  sourceType: string;
  cameraNum: number;
  width: number;
  height: number;
  available: boolean;
  status?: string | null;
}
