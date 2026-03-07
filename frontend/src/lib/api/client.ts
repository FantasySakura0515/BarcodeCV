import axios from "axios";

import type { CameraInfo, DetectionBatch, DetectionObject, DetectionResponse, ModelInfo, StatsSummary } from "@/types";
import { getApiBaseUrl } from "@/lib/api/config";

export const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 60000,
});

export async function fetchStatsSummary() {
  const { data } = await apiClient.get<StatsSummary>("/stats/summary");
  return data;
}

export async function fetchModels() {
  const { data } = await apiClient.get<{ items: ModelInfo[] }>("/models");
  return data.items;
}

export async function fetchCameras(): Promise<CameraInfo[]> {
  // Use native fetch with an explicit AbortSignal timeout.
  // This avoids the axios baseURL SSR-initialisation issue where
  // getApiBaseUrl() might be evaluated server-side (window undefined)
  // and bake in the wrong base URL for the browser axios instance.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  try {
    const res = await fetch("/api/cameras", {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const json = await res.json() as { items: CameraInfo[] };
    return json.items;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchBatches() {
  const { data } = await apiClient.get<{ items: DetectionBatch[] }>("/detections");
  return data.items;
}

export async function fetchBatch(rid: string) {
  const { data } = await apiClient.get<DetectionBatch>(`/detections/${rid}`);
  return data;
}

export async function fetchObject(bid: string) {
  const { data } = await apiClient.get<DetectionObject>(`/objects/${bid}`);
  return data;
}

export async function runDetection(file: File, modelType = "opencv") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("modelType", modelType);

  const { data } = await apiClient.post<DetectionResponse>("/detections", formData);
  return data;
}

export async function previewDetection(file: File, modelType = "opencv") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("modelType", modelType);

  const { data } = await apiClient.post<DetectionResponse>("/live-preview-detection", formData);
  return data;
}

export async function updateObjectRemark(bid: string, remark: string) {
  const { data } = await apiClient.patch<DetectionObject>(`/objects/${bid}`, { remark });
  return data;
}

export async function captureLiveDetection(cameraId: string, modelType = "opencv") {
  const formData = new FormData();
  formData.append("modelType", modelType);

  const { data } = await apiClient.post<DetectionResponse>(`/cameras/${cameraId}/capture-detection`, formData);
  return data;
}

export async function fetchLiveCameraDetection(cameraId: string, modelType = "opencv", maxWidth = 640) {
  const { data } = await apiClient.get<DetectionResponse>(`/cameras/${cameraId}/live-detection`, {
    params: { modelType, maxWidth, ts: Date.now() },
  });
  return data;
}
