"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Camera, CameraRotate, Play, Stop, WarningCircle } from "@phosphor-icons/react";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { DetectionCanvas } from "@/components/detection/detection-canvas";
import { ObjectResultTable } from "@/components/detection/object-result-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { captureLiveDetection, fetchCameras, fetchLiveCameraDetection, previewDetection, runDetection } from "@/lib/api/client";
import { resolveApiAssetUrl } from "@/lib/api/config";
import type { CameraInfo, DetectionObject, ImageSize } from "@/types";

type PerformanceMode = "auto" | "low" | "balanced" | "high";

const PERFORMANCE_PROFILES: Record<PerformanceMode, {
  previewIntervalMs: number;
  detectIntervalMs: number;
  previewWidth: number;
  detectWidth: number;
  jpegQuality: number;
}> = {
  auto: { previewIntervalMs: 900, detectIntervalMs: 1800, previewWidth: 640, detectWidth: 640, jpegQuality: 0.72 },
  low: { previewIntervalMs: 1400, detectIntervalMs: 2600, previewWidth: 480, detectWidth: 480, jpegQuality: 0.55 },
  balanced: { previewIntervalMs: 900, detectIntervalMs: 1800, previewWidth: 640, detectWidth: 640, jpegQuality: 0.72 },
  high: { previewIntervalMs: 500, detectIntervalMs: 1100, previewWidth: 960, detectWidth: 960, jpegQuality: 0.85 },
};

interface SurfaceSize {
  width: number;
  height: number;
}

type LiveCameraOption = CameraInfo & {
  sourceScope: "backend" | "browser";
  deviceId?: string;
};

export default function LiveDetectionPage() {
  const [cameras, setCameras] = useState<LiveCameraOption[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [rid, setRid] = useState<string | null>(null);
  const [objects, setObjects] = useState<DetectionObject[]>([]);
  const [selectedBid, setSelectedBid] = useState<string | null>(null);
  const [isLoadingCameras, setIsLoadingCameras] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [performanceMode, setPerformanceMode] = useState<PerformanceMode>("auto");
  const [browserStream, setBrowserStream] = useState<MediaStream | null>(null);
  const [overlaySourceSize, setOverlaySourceSize] = useState<ImageSize | null>(null);
  const [videoNativeSize, setVideoNativeSize] = useState<SurfaceSize>({ width: 0, height: 0 });
  const [videoContainerSize, setVideoContainerSize] = useState<SurfaceSize>({ width: 0, height: 0 });
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoContainerRef = useRef<HTMLDivElement | null>(null);
  const browserStreamRef = useRef<MediaStream | null>(null);
  const browserPreviewUrlRef = useRef<string | null>(null);

  const selectedCamera = useMemo(
    () => cameras.find((item) => item.id === selectedCameraId) ?? null,
    [cameras, selectedCameraId],
  );

  const performanceProfile = useMemo(() => {
    if (performanceMode !== "auto") {
      return PERFORMANCE_PROFILES[performanceMode];
    }

    const connection = typeof navigator !== "undefined"
      ? (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection
      : undefined;

    const isLowEnd =
      (typeof navigator !== "undefined" && navigator.hardwareConcurrency > 0 && navigator.hardwareConcurrency <= 4)
      || connection?.saveData
      || connection?.effectiveType === "2g"
      || connection?.effectiveType === "slow-2g";

    return isLowEnd ? PERFORMANCE_PROFILES.low : PERFORMANCE_PROFILES.balanced;
  }, [performanceMode]);

  useEffect(() => {
    void refreshCameras();
  }, []);

  useEffect(() => {
    return () => {
      stopBrowserStream();
      clearBrowserPreviewUrl();
    };
  }, []);

  useEffect(() => {
    if (!isPreviewing || selectedCamera?.sourceScope !== "browser") {
      return;
    }

    const video = videoRef.current;

    if (!video || !browserStream) {
      return;
    }

    let cancelled = false;

    const syncVideoSize = () => {
      if (cancelled) {
        return;
      }

      const width = video.videoWidth || 0;
      const height = video.videoHeight || 0;

      if (width > 0 && height > 0) {
        setVideoNativeSize({ width, height });
        return;
      }

      window.requestAnimationFrame(syncVideoSize);
    };

    if (video.srcObject !== browserStream) {
      video.srcObject = browserStream;
    }

    syncVideoSize();

    void video.play().catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [browserStream, isPreviewing, selectedCamera?.sourceScope]);

  useEffect(() => {
    const element = videoContainerRef.current;
    if (!element) {
      return;
    }

    const updateSize = () => {
      const rect = element.getBoundingClientRect();
      setVideoContainerSize({ width: rect.width, height: rect.height });
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, [isPreviewing, selectedCamera?.sourceScope]);

  useEffect(() => {
    if (!isPreviewing || !selectedCameraId || !selectedCamera) {
      return;
    }

    let cancelled = false;

    const loop = async () => {
      while (!cancelled) {
        try {
          if (selectedCamera.sourceScope === "backend") {
            const response = await fetchLiveCameraDetection(selectedCameraId, "opencv", performanceProfile.detectWidth);
            if (!cancelled) {
              setObjects(response.objects);
              setOverlaySourceSize(response.sourceImage ?? null);
              setSelectedBid((current) => current ?? response.objects[0]?.bid ?? null);
            }
          } else {
            const response = await previewFromBrowserCamera();
            if (!cancelled) {
              setObjects(response.objects);
              setOverlaySourceSize(response.sourceImage ?? null);
              setSelectedBid((current) => current ?? response.objects[0]?.bid ?? null);
            }
          }
        } catch (err) {
          if (!cancelled) {
            const message = err instanceof Error ? err.message : "即時辨識失敗";
            setError(message);
          }
        }
        // Wait before next tick — adapts naturally to backend speed
        await new Promise((r) => setTimeout(r, cancelled ? 0 : performanceProfile.detectIntervalMs));
      }
    };

    void loop();

    return () => {
      cancelled = true;
    };
  }, [isPreviewing, performanceProfile.detectIntervalMs, performanceProfile.detectWidth, selectedCamera, selectedCameraId]);

  useEffect(() => {
    if (!isPreviewing || !selectedCameraId || selectedCamera?.sourceScope !== "backend") {
      return;
    }

    const updatePreview = () => {
      setPreviewUrl(
        `/api/cameras/${selectedCameraId}/preview?ts=${Date.now()}&maxWidth=${performanceProfile.previewWidth}&quality=${Math.round(performanceProfile.jpegQuality * 100)}`,
      );
    };

    updatePreview();
    const timer = window.setInterval(updatePreview, performanceProfile.previewIntervalMs);
    return () => window.clearInterval(timer);
  }, [isPreviewing, performanceProfile.jpegQuality, performanceProfile.previewIntervalMs, performanceProfile.previewWidth, selectedCamera?.sourceScope, selectedCameraId]);

  const selectedObject = objects.find((item) => item.bid === selectedBid) ?? null;

  function clearBrowserPreviewUrl() {
    if (browserPreviewUrlRef.current) {
      URL.revokeObjectURL(browserPreviewUrlRef.current);
      browserPreviewUrlRef.current = null;
    }
  }

  function updateBrowserPreviewUrl(blob: Blob) {
    clearBrowserPreviewUrl();
    const objectUrl = URL.createObjectURL(blob);
    browserPreviewUrlRef.current = objectUrl;
    setPreviewUrl(objectUrl);
  }

  async function refreshCameras() {
    setIsLoadingCameras(true);
    setError(null);
    try {
      const [backendResult, browserResult] = await Promise.allSettled([
        fetchCameras(),     // already has 10s AbortSignal timeout inside
        getBrowserCameras(),
      ]);

      // Defensive: ensure we always have arrays even if the API returns unexpected data.
      const rawBackend = backendResult.status === "fulfilled" ? backendResult.value : undefined;
      const rawBrowser = browserResult.status === "fulfilled" ? browserResult.value : undefined;
      const backendItems: CameraInfo[] = Array.isArray(rawBackend) ? (rawBackend as CameraInfo[]) : [];
      const browserItems: LiveCameraOption[] = Array.isArray(rawBrowser) ? rawBrowser : [];

      // Log for debugging — visible in browser console.
      console.debug("[refreshCameras] backendResult:", backendResult);
      console.debug("[refreshCameras] browserResult:", browserResult);
      console.debug("[refreshCameras] backendItems:", backendItems, "browserItems:", browserItems);

      if (backendResult.status === "rejected") {
        const msg = backendResult.reason instanceof Error ? backendResult.reason.message : "無法連線到後端";
        setError(`後端鏡頭載入失敗：${msg}`);
      } else if (!Array.isArray(rawBackend)) {
        // fetchCameras() resolved but returned non-array — log for diagnosis.
        console.warn("[refreshCameras] fetchCameras() resolved with non-array:", rawBackend);
        setError(`後端回應格式異常（非陣列）：${JSON.stringify(rawBackend)?.slice(0, 120)}`);
      }

      const items: LiveCameraOption[] = [
        ...browserItems,
        ...backendItems.map((item) => ({
          ...item,
          sourceScope: "backend" as const,
        })),
      ];

      console.debug("[refreshCameras] final items:", items);
      setCameras(items);

      const preferred = items.find((item) => item.id === selectedCameraId && item.available)
        ?? items.find((item) => item.available)
        ?? items[0]
        ?? null;

      setSelectedCameraId(preferred?.id ?? "");
    } catch (err) {
      const message = err instanceof Error ? err.message : "無法取得鏡頭清單";
      console.error("[refreshCameras] unexpected error:", err);
      setError(message);
    } finally {
      setIsLoadingCameras(false);
    }
  }

  function startPreview() {
    if (!selectedCameraId || !selectedCamera) {
      setError("請先選擇可用鏡頭");
      return;
    }

    setObjects([]);
    setSelectedBid(null);
    setRid(null);
    setOverlaySourceSize(null);
    setError(null);

    if (selectedCamera.sourceScope === "browser") {
      clearBrowserPreviewUrl();
      setPreviewUrl(null);
      setIsPreviewing(true);
      void startBrowserPreview(selectedCamera);
      return;
    }

    stopBrowserStream();
    setPreviewUrl(null);
    setIsPreviewing(true);
  }

  function stopPreview() {
    setIsPreviewing(false);
    stopBrowserStream();
    setOverlaySourceSize(null);
  }

  async function captureCurrentFrame() {
    if (!selectedCameraId || !selectedCamera) {
      setError("請先選擇可用鏡頭");
      return;
    }

    setIsCapturing(true);
    setError(null);
    try {
      const response = selectedCamera.sourceScope === "browser"
        ? await captureFromBrowserCamera(selectedCamera)
        : await captureLiveDetection(selectedCameraId);

      setIsPreviewing(false);
      stopBrowserStream();
      setRid(response.rid);
      setObjects(response.objects);
      setOverlaySourceSize(response.sourceImage ?? null);
      setSelectedBid(response.objects[0]?.bid ?? null);
      clearBrowserPreviewUrl();
      setPreviewUrl(resolveApiAssetUrl(response.imagePath) ?? null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "擷取並辨識失敗";
      setError(message);
    } finally {
      setIsCapturing(false);
    }
  }

  async function startBrowserPreview(camera: LiveCameraOption) {
    try {
      stopBrowserStream();
      clearBrowserPreviewUrl();
      setPreviewUrl(null);

      const stream = await navigator.mediaDevices.getUserMedia({
        video: camera.deviceId
          ? {
              deviceId: { exact: camera.deviceId },
              width: { ideal: camera.width || 1280 },
              height: { ideal: camera.height || 720 },
            }
          : true,
        audio: false,
      });

      browserStreamRef.current = stream;
      setBrowserStream(stream);
      setError(null);

      const refreshedBrowser = await getBrowserCameras();
      setCameras((current) => {
        const backend = current.filter((item) => item.sourceScope === "backend");
        return [...refreshedBrowser, ...backend];
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "無法開啟裝置鏡頭";
      setError(`無法開啟裝置鏡頭: ${message}`);
      setBrowserStream(null);
      setIsPreviewing(false);
    }
  }

  function stopBrowserStream() {
    browserStreamRef.current?.getTracks().forEach((track) => track.stop());
    browserStreamRef.current = null;
    setBrowserStream(null);
    setVideoNativeSize({ width: 0, height: 0 });
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  async function captureFromBrowserCamera(camera: LiveCameraOption) {
    const video = videoRef.current;
    if (!video || !browserStreamRef.current) {
      throw new Error("請先開始裝置鏡頭預覽");
    }

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    const canvas = document.createElement("canvas");
    const targetWidth = Math.min(width, 1280);
    const targetHeight = Math.max(1, Math.round((height / width) * targetWidth));
    canvas.width = targetWidth;
    canvas.height = targetHeight;

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("無法建立擷取畫布");
    }

    context.drawImage(video, 0, 0, targetWidth, targetHeight);

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", 0.88);
    });

    if (!blob) {
      throw new Error("無法擷取目前畫面");
    }

    const file = new File([blob], `${camera.id}-${Date.now()}.jpg`, { type: "image/jpeg" });
    return runDetection(file);
  }

  async function previewFromBrowserCamera() {
    const video = videoRef.current;
    if (!video || !browserStreamRef.current) {
      throw new Error("請先開始裝置鏡頭預覽");
    }

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;

    const canvas = document.createElement("canvas");
    const targetWidth = Math.min(width, performanceProfile.detectWidth);
    const targetHeight = Math.max(1, Math.round((height / width) * targetWidth));
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("無法建立即時辨識畫布");
    }

    context.drawImage(video, 0, 0, targetWidth, targetHeight);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", performanceProfile.jpegQuality);
    });

    if (!blob) {
      throw new Error("無法擷取即時辨識畫面");
    }
    const file = new File([blob], `live-preview-${Date.now()}.jpg`, { type: "image/jpeg" });
    return previewDetection(file);
  }

  const browserFrame = useMemo(() => {
    if (!videoNativeSize.width || !videoNativeSize.height || !videoContainerSize.width || !videoContainerSize.height) {
      return null;
    }

    const containerRatio = videoContainerSize.width / videoContainerSize.height;
    const videoRatio = videoNativeSize.width / videoNativeSize.height;

    if (containerRatio > videoRatio) {
      const height = videoContainerSize.height;
      const width = height * videoRatio;
      return { width, height, left: (videoContainerSize.width - width) / 2, top: 0 };
    }

    const width = videoContainerSize.width;
    const height = width / videoRatio;
    return { width, height, left: 0, top: (videoContainerSize.height - height) / 2 };
  }, [videoNativeSize, videoContainerSize]);

  const liveOverlaySourceSize = overlaySourceSize
    ?? (videoNativeSize.width && videoNativeSize.height ? videoNativeSize : null);

  return (
    <div className="space-y-6">
      <PageHeader
        badge="Camera / Device Capture"
        title="即時辨識"
        description="支援後端鏡頭與目前裝置本身鏡頭。啟動預覽後按下擷取，會將當前畫面送到後端辨識並存入批次紀錄。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void refreshCameras()} disabled={isLoadingCameras || isCapturing}>
              <CameraRotate size={16} />
              重新掃描鏡頭
            </Button>
            {isPreviewing ? (
              <Button variant="outline" onClick={stopPreview} disabled={isCapturing}>
                <Stop size={16} />
                停止預覽
              </Button>
            ) : (
              <Button onClick={startPreview} disabled={!selectedCamera?.available || isCapturing}>
                <Play size={16} />
                開始即時辨識
              </Button>
            )}
            <Button onClick={() => void captureCurrentFrame()} disabled={!selectedCamera?.available || isCapturing}>
              <Camera size={16} />
              {isCapturing ? "擷取中..." : "擷取並存檔辨識"}
            </Button>
          </div>
        }
      />

      <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <div className="space-y-6">
          <SectionCard title="鏡頭來源" description="系統會列出目前可存取的後端鏡頭，以及瀏覽器所在設備本身的鏡頭。">
            <div className="space-y-4 text-sm">
              <div className="space-y-2">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">目前鏡頭</label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-input/20 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  value={selectedCameraId}
                  onChange={(event) => {
                    setSelectedCameraId(event.target.value);
                    setIsPreviewing(false);
                    setObjects([]);
                    setSelectedBid(null);
                    setRid(null);
                    setOverlaySourceSize(null);
                    clearBrowserPreviewUrl();
                    setPreviewUrl(null);
                  }}
                >
                  {!cameras.length ? <option value="">目前沒有鏡頭</option> : null}
                  {cameras.map((camera) => (
                    <option key={camera.id} value={camera.id} disabled={!camera.available}>
                      [{camera.sourceScope === "browser" ? "裝置" : "主機"}] {camera.label} {camera.available ? "" : "（不可用）"}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  {isLoadingCameras
                    ? "正在掃描鏡頭..."
                    : cameras.length > 0
                      ? `已偵測到 ${cameras.length} 個鏡頭（後端 ${cameras.filter((c) => c.sourceScope === "backend").length} 個，裝置 ${cameras.filter((c) => c.sourceScope === "browser").length} 個）`
                      : "未偵測到任何鏡頭，請點擊「重新掃描鏡頭」"}
                </p>
                {error && !isLoadingCameras ? (
                  <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
                    ⚠ {error}
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">效能模式</label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-input/20 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  value={performanceMode}
                  onChange={(event) => setPerformanceMode(event.target.value as PerformanceMode)}
                >
                  <option value="auto">自動</option>
                  <option value="low">低耗能 / 弱網路</option>
                  <option value="balanced">平衡</option>
                  <option value="high">高更新率</option>
                </select>
              </div>

              {selectedCamera ? (
                <div className="space-y-3 rounded-2xl border bg-background/50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">{selectedCamera.label}</p>
                    <Badge variant={selectedCamera.available ? "success" : "outline"}>
                      {selectedCamera.available ? "可用" : "不可用"}
                    </Badge>
                  </div>
                  <p className="text-muted-foreground">範圍：{selectedCamera.sourceScope === "browser" ? "目前設備鏡頭" : "後端主機鏡頭"}</p>
                  <p className="text-muted-foreground">來源：{selectedCamera.sourceType} / index {selectedCamera.cameraNum}</p>
                  <p className="text-muted-foreground">解析度：{selectedCamera.width} × {selectedCamera.height}</p>
                  <p className="text-muted-foreground">模式：{performanceMode === "auto" ? "自動" : performanceMode} / 預覽 {performanceProfile.previewWidth}px / 辨識 {performanceProfile.detectWidth}px</p>
                  {selectedCamera.status ? <p className="wrap-break-word text-xs text-muted-foreground">狀態：{selectedCamera.status}</p> : null}
                </div>
              ) : null}

              <div className="rounded-2xl border bg-muted/20 p-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">本次擷取摘要</p>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">RID：<span className="font-medium text-foreground">{rid ?? "尚未擷取"}</span></p>
                  <p className="text-sm text-muted-foreground">物件數量：<span className="font-medium text-foreground">{objects.length}</span></p>
                  <p className="text-sm text-muted-foreground">目前選取：<span className="font-medium break-all text-foreground">{selectedObject?.bid ?? "無"}</span></p>
                </div>
              </div>

              {error ? (
                <div className="flex items-start gap-2 rounded-2xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  <WarningCircle size={18} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              ) : null}
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <SectionCard title="鏡頭畫面" description="裝置鏡頭會直接顯示瀏覽器預覽；後端鏡頭則透過 API 取回最新影格。擷取後會顯示已存檔的辨識結果影像。">
            {isPreviewing && selectedCamera?.sourceScope === "browser" ? (
              <div className="relative overflow-hidden rounded-3xl border bg-card/70 p-3 shadow-sm">
                <div ref={videoContainerRef} className="relative h-[min(62vh,40rem)] min-h-80 overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#f8fafc,#dbeafe)] dark:bg-[linear-gradient(135deg,#0f172a,#1e293b)]">
                  <video
                    ref={videoRef}
                    className="relative z-0 h-full w-full object-contain"
                    autoPlay
                    muted
                    playsInline
                    onLoadedMetadata={(event) => {
                      setVideoNativeSize({
                        width: event.currentTarget.videoWidth || 1280,
                        height: event.currentTarget.videoHeight || 720,
                      });
                    }}
                  />

                  <div className="pointer-events-none absolute inset-0 z-20">
                    {browserFrame && liveOverlaySourceSize
                      ? objects.map((item) => {
                          const bw = Math.max(item.bbox.x2 - item.bbox.x1, 12);
                          const bh = Math.max(item.bbox.y2 - item.bbox.y1, 12);
                          const active = item.bid === selectedBid;

                          return (
                            <button
                              key={item.bid}
                              type="button"
                              onClick={() => setSelectedBid(item.bid)}
                              className={`pointer-events-auto absolute rounded-xl border-2 text-left outline-none transition-all ${active ? "border-sky-400 shadow-[0_0_0_9999px_rgba(15,23,42,0.12)]" : "border-emerald-400/90 hover:border-emerald-300"}`}
                              style={{
                                left: browserFrame.left + (item.bbox.x1 / liveOverlaySourceSize.width) * browserFrame.width,
                                top: browserFrame.top + (item.bbox.y1 / liveOverlaySourceSize.height) * browserFrame.height,
                                width: (bw / liveOverlaySourceSize.width) * browserFrame.width,
                                height: (bh / liveOverlaySourceSize.height) * browserFrame.height,
                              }}
                            >
                              <span className="absolute -top-7 left-0 max-w-40 truncate rounded-full bg-background/95 px-2 py-1 text-[10px] font-medium shadow-sm">
                                {item.bid}
                              </span>
                            </button>
                          );
                        })
                      : null}
                  </div>
                </div>
              </div>
            ) : (
              <DetectionCanvas
                imageUrl={previewUrl}
                objects={objects}
                selectedBid={selectedBid}
                onSelect={setSelectedBid}
                sourceImageSize={overlaySourceSize}
              />
            )}
          </SectionCard>

          <SectionCard title="辨識結果列表" description="按下擷取後，當前影格的辨識結果會存入後端資料庫。">
            {objects.length ? (
              <ObjectResultTable items={objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
            ) : (
              <EmptyState
                title={isLoadingCameras ? "正在載入鏡頭" : "尚未取得即時辨識結果"}
                description="開始即時辨識後，系統會持續把物件框選結果回傳到前端顯示；按下擷取才會正式存入資料庫。"
              />
            )}
          </SectionCard>
        </div>
      </section>
    </div>
  );
}

async function getBrowserCameras(): Promise<LiveCameraOption[]> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
    return [];
  }

  // mediaDevices API requires a secure context (HTTPS or localhost).
  // On Pi accessed via http://192.168.x.x:3000, this will be unavailable.
  if (typeof window !== "undefined" && !window.isSecureContext) {
    return [];
  }

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoInputs = devices.filter((device) => device.kind === "videoinput");

    return videoInputs.map((device, index) => ({
      id: `browser-${device.deviceId || index}`,
      label: device.label || `設備鏡頭 ${index + 1}`,
      sourceType: "browser",
      sourceScope: "browser",
      deviceId: device.deviceId,
      cameraNum: index,
      width: 1280,
      height: 720,
      available: true,
      status: device.label ? "可直接使用" : "首次使用時將要求鏡頭權限",
    }));
  } catch {
    return [];
  }
}