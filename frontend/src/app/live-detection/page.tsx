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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { captureLiveDetection, fetchCameras, fetchLiveCameraDetection, previewDetection, runDetection } from "@/lib/api/client";
import { resolveApiAssetUrl } from "@/lib/api/config";
import type { CameraInfo, DetectionObject, ImageSize } from "@/types";

type PerformanceMode = "auto" | "low" | "balanced" | "high";

/** Only concrete profiles — "auto" resolves at runtime to "low" or "balanced" based on hardware / network. */
const PERFORMANCE_PROFILES: Record<Exclude<PerformanceMode, "auto">, {
  /**
   * Minimum total cycle time (ms). Next detection starts as soon as
   * max(minCycleMs - detectionTime, 50) has elapsed — so detectIntervalMs
   * is the TOTAL period, not an extra delay added after detection completes.
   */
  minCycleMs: number;
  /** Scale factor applied to the camera resolution for the MJPEG preview stream. */
  previewScale: number;
  /** Scale factor applied to the camera resolution for each detection request. */
  detectScale: number;
  /** JPEG quality sent to the backend (0–1). */
  jpegQuality: number;
}> = {
  //                  total cycle  preview res  detect res   JPEG Q
  low:      { minCycleMs: 2000, previewScale: 0.45, detectScale: 0.35, jpegQuality: 0.60 },
  balanced: { minCycleMs: 800,  previewScale: 0.65, detectScale: 0.55, jpegQuality: 0.75 },
  high:     { minCycleMs: 400,  previewScale: 0.85, detectScale: 0.72, jpegQuality: 0.85 },
};

const PERFORMANCE_MODE_LABELS: Record<Exclude<PerformanceMode, "auto">, string> = {
  low:      "低耗能",
  balanced: "平衡",
  high:     "高效能",
};

interface SurfaceSize {
  width: number;
  height: number;
}

type LiveCameraOption = CameraInfo & {
  sourceScope: "backend" | "browser";
  deviceId?: string;
};

function scaleDimension(value: number, scale: number, minimum = 320) {
  if (!Number.isFinite(value) || value <= 0) {
    return minimum;
  }

  return Math.min(value, Math.max(minimum, Math.round(value * scale)));
}

/**
 * Merge newly detected objects into the stable set.
 * - Objects with a decoded barcodeValue are kept indefinitely (stable bbox wins on update).
 * - Incoming barcodes always update the bbox so display tracks movement.
 */
function mergeStableObjects(
  stable: DetectionObject[],
  incoming: DetectionObject[],
): DetectionObject[] {
  const byValue = new Map<string, DetectionObject>();
  for (const obj of stable) {
    if (obj.barcodeValue) byValue.set(obj.barcodeValue, obj);
  }
  for (const obj of incoming) {
    if (obj.barcodeValue) byValue.set(obj.barcodeValue, obj); // fresh bbox wins
  }
  // Normalise bid to barcodeValue so every entry in stableObjects has a
  // globally-unique, frame-independent key — prevents React duplicate-key
  // warnings when different frames assign different bids to the same barcode.
  return [...byValue.values()].map((obj) => ({ ...obj, bid: obj.barcodeValue! }));
}

function buildOverlayLines(item: DetectionObject, showDecodeInfo: boolean) {
  if (!showDecodeInfo) {
    return [];
  }

  return [item.bid];
}

export default function LiveDetectionPage() {
  const [cameras, setCameras] = useState<LiveCameraOption[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [rid, setRid] = useState<string | null>(null);
  const [objects, setObjects] = useState<DetectionObject[]>([]);
  /** Accumulated decoded barcodes across frames — never flickers out once found. */
  const [stableObjects, setStableObjects] = useState<DetectionObject[]>([]);
  const [selectedBid, setSelectedBid] = useState<string | null>(null);
  const [isLoadingCameras, setIsLoadingCameras] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [isScanningLive, setIsScanningLive] = useState(false);
  const [lastScanInfo, setLastScanInfo] = useState<{ count: number; elapsedMs: number; at: Date } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [performanceMode, setPerformanceMode] = useState<PerformanceMode>("auto");
  const [browserStream, setBrowserStream] = useState<MediaStream | null>(null);
  const [overlaySourceSize, setOverlaySourceSize] = useState<ImageSize | null>(null);
  const [videoNativeSize, setVideoNativeSize] = useState<SurfaceSize>({ width: 0, height: 0 });
  const [videoContainerSize, setVideoContainerSize] = useState<SurfaceSize>({ width: 0, height: 0 });
  const [autoResolvedMode, setAutoResolvedMode] = useState<Exclude<PerformanceMode, "auto">>("balanced");
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [showDecodeInfo, setShowDecodeInfo] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoContainerRef = useRef<HTMLDivElement | null>(null);
  const browserStreamRef = useRef<MediaStream | null>(null);
  const browserPreviewUrlRef = useRef<string | null>(null);
  const previewSessionRef = useRef(0);

  const selectedCamera = useMemo(
    () => cameras.find((item) => item.id === selectedCameraId) ?? null,
    [cameras, selectedCameraId],
  );

  /**
   * Keep SSR and the first client render deterministic. Resolve the real
   * automatic mode only after mount, based on client hardware / network.
   */
  useEffect(() => {
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;

    const isLowEnd =
      (navigator.hardwareConcurrency > 0 && navigator.hardwareConcurrency <= 4)
      || connection?.saveData
      || connection?.effectiveType === "2g"
      || connection?.effectiveType === "slow-2g";

    setAutoResolvedMode(isLowEnd ? "low" : "balanced");
  }, []);

  const resolvedMode = performanceMode === "auto" ? autoResolvedMode : performanceMode;

  const performanceProfile = useMemo(
    () => PERFORMANCE_PROFILES[resolvedMode],
    [resolvedMode],
  );

  const selectedCameraSurface = useMemo(() => {
    if (selectedCamera?.sourceScope === "backend" && overlaySourceSize?.width && overlaySourceSize.height) {
      return overlaySourceSize;
    }

    if (selectedCamera?.sourceScope === "browser" && videoNativeSize.width > 0 && videoNativeSize.height > 0) {
      return videoNativeSize;
    }

    if (selectedCamera?.width && selectedCamera.height) {
      return {
        width: selectedCamera.width,
        height: selectedCamera.height,
      };
    }

    return null;
  }, [overlaySourceSize, selectedCamera, videoNativeSize]);

  const performanceTargetSize = useMemo(() => {
    if (!selectedCameraSurface) {
      return null;
    }

    return {
      preview: {
        width: scaleDimension(selectedCameraSurface.width, performanceProfile.previewScale),
        height: scaleDimension(selectedCameraSurface.height, performanceProfile.previewScale, 180),
      },
      detect: {
        width: scaleDimension(selectedCameraSurface.width, performanceProfile.detectScale),
        height: scaleDimension(selectedCameraSurface.height, performanceProfile.detectScale, 180),
      },
    };
  }, [performanceProfile.detectScale, performanceProfile.previewScale, selectedCameraSurface]);

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

    const sessionId = ++previewSessionRef.current;
    let cancelled = false;

    const loop = async () => {
      while (!cancelled) {
        const cycleStart = Date.now();
        try {
          if (!cancelled && previewSessionRef.current === sessionId) setIsScanningLive(true);
          if (selectedCamera.sourceScope === "backend") {
            const response = await fetchLiveCameraDetection(
              selectedCameraId,
              "opencv",
              performanceTargetSize?.detect.width ?? scaleDimension(selectedCamera?.width ?? 0, performanceProfile.detectScale),
            );
            if (!cancelled && previewSessionRef.current === sessionId) {
              const elapsedMs = Date.now() - cycleStart;
              syncCameraActualResolution(selectedCameraId, response.sourceImage);
              setObjects(response.objects);
              setStableObjects((prev) => mergeStableObjects(prev, response.objects));
              setOverlaySourceSize(response.sourceImage ?? null);
              setSelectedBid((current) => current ?? response.objects[0]?.bid ?? null);
              setLastScanInfo({ count: response.objects.length, elapsedMs, at: new Date() });
              setError(null);
            }
          } else {
            const response = await previewFromBrowserCamera();
            if (!cancelled && previewSessionRef.current === sessionId) {
              const elapsedMs = Date.now() - cycleStart;
              setObjects(response.objects);
              setStableObjects((prev) => mergeStableObjects(prev, response.objects));
              setOverlaySourceSize(response.sourceImage ?? null);
              setSelectedBid((current) => current ?? response.objects[0]?.bid ?? null);
              setLastScanInfo({ count: response.objects.length, elapsedMs, at: new Date() });
              setError(null);
            }
          }
        } catch (err) {
          if (!cancelled && previewSessionRef.current === sessionId) {
            const message = err instanceof Error ? err.message : "即時辨識失敗";
            setError(message);
          }
        } finally {
          if (!cancelled && previewSessionRef.current === sessionId) setIsScanningLive(false);
        }
        // Wait only the remaining time so that minCycleMs is the TOTAL period,
        // not an extra delay added after detection. Minimum 50ms to yield the
        // event loop even when detection is faster than the cycle target.
        const elapsed = Date.now() - cycleStart;
        const remaining = Math.max(50, performanceProfile.minCycleMs - elapsed);
        await new Promise((r) => setTimeout(r, cancelled ? 0 : remaining));
      }
    };

    void loop();

    return () => {
      cancelled = true;
      if (previewSessionRef.current === sessionId) {
        previewSessionRef.current += 1;
      }
      setIsScanningLive(false);
    };
  }, [isPreviewing, performanceProfile.minCycleMs, performanceProfile.detectScale, performanceTargetSize, selectedCamera, selectedCameraId]);

  // MJPEG stream URL for backend cameras — browser handles frame updates natively.
  // Detection runs concurrently by reading the server-side frame cache.
  const streamUrl = useMemo(() => {
    if (!isPreviewing || !selectedCameraId || selectedCamera?.sourceScope !== "backend") {
      return null;
    }
    const previewWidth = performanceTargetSize?.preview.width
      ?? scaleDimension(selectedCamera?.width ?? 0, performanceProfile.previewScale);

    return `/api/cameras/${selectedCameraId}/stream?maxWidth=${previewWidth}&quality=${Math.round(performanceProfile.jpegQuality * 100)}`;
  }, [isPreviewing, performanceProfile.jpegQuality, performanceProfile.previewScale, performanceTargetSize, selectedCamera?.sourceScope, selectedCamera?.width, selectedCameraId]);

  const displayObjects = isPreviewing ? stableObjects : objects;
  const selectedObject = displayObjects.find((item) => item.bid === selectedBid) ?? null;

  function invalidatePreviewSession() {
    previewSessionRef.current += 1;
  }

  function resetLiveOverlayState() {
    setIsScanningLive(false);
    setLastScanInfo(null);
    setStableObjects([]);
    setOverlaySourceSize(null);
  }

  function handleCameraChange(cameraId: string) {
    invalidatePreviewSession();
    stopBrowserStream();
    setSelectedCameraId(cameraId);
    setIsPreviewing(false);
    setObjects([]);
    setStableObjects([]);
    setSelectedBid(null);
    setRid(null);
    setOverlaySourceSize(null);
    clearBrowserPreviewUrl();
    setPreviewUrl(null);
  }

  function syncCameraActualResolution(cameraId: string, sourceImage?: ImageSize | null) {
    if (!sourceImage?.width || !sourceImage.height) {
      return;
    }

    setCameras((current) => current.map((camera) => {
      if (camera.id !== cameraId) {
        return camera;
      }

      if (camera.width === sourceImage.width && camera.height === sourceImage.height) {
        return camera;
      }

      return {
        ...camera,
        width: sourceImage.width,
        height: sourceImage.height,
      };
    }));
  }

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
        fetchCameras(),
        getBrowserCameras(),
      ]);

      const rawBackend = backendResult.status === "fulfilled" ? backendResult.value : undefined;
      const rawBrowser = browserResult.status === "fulfilled" ? browserResult.value : undefined;
      const backendItems: CameraInfo[] = Array.isArray(rawBackend) ? (rawBackend as CameraInfo[]) : [];
      const browserItems: LiveCameraOption[] = Array.isArray(rawBrowser) ? rawBrowser : [];

      if (backendResult.status === "rejected") {
        const msg = backendResult.reason instanceof Error ? backendResult.reason.message : "無法連線到後端";
        setError(`後端鏡頭載入失敗：${msg}`);
      } else if (!Array.isArray(rawBackend)) {
        setError(`後端回應格式異常（非陣列）：${JSON.stringify(rawBackend)?.slice(0, 120)}`);
      }

      const items: LiveCameraOption[] = [
        ...browserItems,
        ...backendItems.map((item) => ({
          ...item,
          sourceScope: "backend" as const,
        })),
      ];

      setCameras(items);

      const preferred = items.find((item) => item.id === selectedCameraId && item.available)
        ?? items.find((item) => item.available)
        ?? items[0]
        ?? null;

      setSelectedCameraId(preferred?.id ?? "");
    } catch (err) {
      const message = err instanceof Error ? err.message : "無法取得鏡頭清單";
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

    invalidatePreviewSession();
    setObjects([]);
    resetLiveOverlayState();
    setSelectedBid(null);
    setRid(null);
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
    invalidatePreviewSession();
    setIsPreviewing(false);
    resetLiveOverlayState();
    stopBrowserStream();
  }

  async function captureCurrentFrame() {
    if (!selectedCameraId || !selectedCamera) {
      setError("請先選擇可用鏡頭");
      return;
    }

    setIsCapturing(true);
    setError(null);
    try {
      invalidatePreviewSession();

      if (selectedCamera.sourceScope === "browser") {
        const snapshot = await captureBrowserSnapshot(selectedCamera, 0.88, Math.min(videoRef.current?.videoWidth || 1280, 1280));
        updateBrowserPreviewUrl(snapshot.blob);
        setPreviewUrl(browserPreviewUrlRef.current);
        setIsPreviewing(false);
        resetLiveOverlayState();
        stopBrowserStream();

        const response = await runDetection(snapshot.file);
        setRid(response.rid);
        setObjects(response.objects);
        setOverlaySourceSize(response.sourceImage ?? snapshot.sourceImage);
        setSelectedBid(response.objects[0]?.bid ?? null);

        if (response.imagePath) {
          clearBrowserPreviewUrl();
          setPreviewUrl(resolveApiAssetUrl(response.imagePath) ?? null);
        }
      } else {
        setIsPreviewing(false);
        resetLiveOverlayState();
        const response = await captureLiveDetection(selectedCameraId);
        syncCameraActualResolution(selectedCameraId, response.sourceImage);
        setRid(response.rid);
        setObjects(response.objects);
        setOverlaySourceSize(response.sourceImage ?? null);
        setSelectedBid(response.objects[0]?.bid ?? null);
        clearBrowserPreviewUrl();
        setPreviewUrl(resolveApiAssetUrl(response.imagePath) ?? null);
      }
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

      const [videoTrack] = stream.getVideoTracks();
      const settings = videoTrack?.getSettings();
      const streamWidth = typeof settings?.width === "number" ? settings.width : camera.width;
      const streamHeight = typeof settings?.height === "number" ? settings.height : camera.height;

      browserStreamRef.current = stream;
      setBrowserStream(stream);
      setVideoNativeSize({ width: streamWidth || 0, height: streamHeight || 0 });
      setError(null);

      const refreshedBrowser = await getBrowserCameras();
      setCameras((current) => {
        const backend = current.filter((item) => item.sourceScope === "backend");
        return [
          ...refreshedBrowser.map((item) => item.id === camera.id
            ? {
                ...item,
                width: streamWidth || item.width,
                height: streamHeight || item.height,
              }
            : item),
          ...backend,
        ];
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

  async function captureBrowserSnapshot(camera: LiveCameraOption, quality: number, maxWidth: number) {
    const video = videoRef.current;
    if (!video || !browserStreamRef.current) {
      throw new Error("請先開始裝置鏡頭預覽");
    }

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    const canvas = document.createElement("canvas");
    const targetWidth = Math.min(width, maxWidth);
    const targetHeight = Math.max(1, Math.round((height / width) * targetWidth));
    canvas.width = targetWidth;
    canvas.height = targetHeight;

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("無法建立擷取畫布");
    }

    context.drawImage(video, 0, 0, targetWidth, targetHeight);

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", quality);
    });

    if (!blob) {
      throw new Error("無法擷取目前畫面");
    }

    const file = new File([blob], `${camera.id}-${Date.now()}.jpg`, { type: "image/jpeg" });
    return {
      blob,
      file,
      sourceImage: {
        width: targetWidth,
        height: targetHeight,
      },
    };
  }

  async function previewFromBrowserCamera() {
    if (!selectedCamera) {
      throw new Error("請先選擇可用鏡頭");
    }

    const snapshot = await captureBrowserSnapshot(
      selectedCamera,
      performanceProfile.jpegQuality,
      scaleDimension(videoRef.current?.videoWidth || 1280, performanceProfile.detectScale),
    );
    return previewDetection(snapshot.file);
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
        badge="鏡頭／裝置擷取"
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
                <Select value={selectedCameraId || undefined} onValueChange={handleCameraChange} disabled={!cameras.length}>
                  <SelectTrigger className="h-10 w-full px-3 text-sm">
                    <SelectValue placeholder="目前沒有鏡頭" />
                  </SelectTrigger>
                  <SelectContent>
                    {cameras.map((camera) => (
                      <SelectItem key={camera.id} value={camera.id} disabled={!camera.available}>
                        [{camera.sourceScope === "browser" ? "裝置" : "主機"}] {camera.label} {camera.available ? "" : "（不可用）"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                <Select value={performanceMode} onValueChange={(value) => setPerformanceMode(value as PerformanceMode)}>
                  <SelectTrigger className="h-10 w-full px-3 text-sm">
                    <SelectValue placeholder="選擇效能模式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">自動（依裝置與網路偵測）</SelectItem>
                    <SelectItem value="low">低耗能 — 省頻寬 / 弱網路</SelectItem>
                    <SelectItem value="balanced">平衡 — 適合大多數場景</SelectItem>
                    <SelectItem value="high">高效能 — 快速偵測 / 高解析</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {performanceMode === "auto"
                    ? `自動已解析為「${PERFORMANCE_MODE_LABELS[autoResolvedMode]}」模式`
                    : `最小周期 ${(performanceProfile.minCycleMs / 1000).toFixed(1)} 秒 / 品質 ${Math.round(performanceProfile.jpegQuality * 100)}%`}
                </p>
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
                  <p className="text-muted-foreground">來源：{selectedCamera.sourceType} / 編號 {selectedCamera.cameraNum}</p>
                  <p className="text-muted-foreground">解析度：{selectedCamera.width} × {selectedCamera.height}</p>
                  <p className="text-muted-foreground">
                    模式：
                    {performanceMode === "auto"
                      ? `自動 → ${PERFORMANCE_MODE_LABELS[autoResolvedMode]}`
                      : PERFORMANCE_MODE_LABELS[resolvedMode]}
                  </p>
                  <p className="text-muted-foreground">
                    最小周期：{(performanceProfile.minCycleMs / 1000).toFixed(1)} 秒（偵測完成即進行下一張）
                  </p>
                  <p className="text-muted-foreground">
                    {performanceTargetSize
                      ? `預覽 ${performanceTargetSize.preview.width}×${performanceTargetSize.preview.height}（${Math.round(performanceProfile.previewScale * 100)}%）／辨識 ${performanceTargetSize.detect.width}×${performanceTargetSize.detect.height}（${Math.round(performanceProfile.detectScale * 100)}%）`
                      : `預覽 ${Math.round(performanceProfile.previewScale * 100)}%／辨識 ${Math.round(performanceProfile.detectScale * 100)}%`}
                  </p>
                  {selectedCamera.status ? <p className="wrap-break-word text-xs text-muted-foreground">狀態：{selectedCamera.status}</p> : null}
                </div>
              ) : null}

              {isPreviewing ? (
                <div className="rounded-2xl border bg-muted/20 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">即時掃描狀態</p>
                    {isScanningLive ? (
                      <span className="flex items-center gap-1.5 text-xs font-medium text-sky-500">
                        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-sky-500" />
                        掃描中…
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
                        待命
                      </span>
                    )}
                  </div>
                  <div className="space-y-2">
                    {lastScanInfo ? (
                      <>
                        <p className="text-sm text-muted-foreground">最後掃描結果：<span className="font-medium text-foreground">{lastScanInfo.count} 個物件</span></p>
                        <p className="text-sm text-muted-foreground">耗時：<span className="font-medium text-foreground">{lastScanInfo.elapsedMs} ms</span></p>
                        <p className="text-sm text-muted-foreground">時刻：<span className="font-medium text-foreground">{lastScanInfo.at.toLocaleTimeString()}</span></p>
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">等待第一次掃描…</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border bg-muted/20 p-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">本次擷取摘要</p>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">RID：<span className="font-medium text-foreground">{rid ?? "尚未擷取"}</span></p>
                    <p className="text-sm text-muted-foreground">物件數量：<span className="font-medium text-foreground">{objects.length}</span></p>
                    <p className="text-sm text-muted-foreground">目前選取：<span className="font-medium break-all text-foreground">{selectedObject?.bid ?? "無"}</span></p>
                  </div>
                </div>
              )}

              {error ? (
                <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  <div className="flex items-start gap-2">
                    <WarningCircle size={18} className="mt-0.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                  <Button size="sm" variant="outline" className="mt-2" onClick={() => void refreshCameras()}>
重新掃描鏡頭
                  </Button>
                </div>
              ) : null}
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <SectionCard title="鏡頭畫面" description="裝置鏡頭會直接顯示瀏覽器預覽；後端鏡頭則透過 API 取回最新影格。擷取後會顯示已存檔的辨識結果影像。">
            <div className="mb-4 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={showBoundingBoxes ? "default" : "outline"}
                onClick={() => setShowBoundingBoxes((current) => !current)}
              >
                {showBoundingBoxes ? "隱藏物件框" : "顯示物件框"}
              </Button>
              <Button
                size="sm"
                variant={showDecodeInfo ? "default" : "outline"}
                onClick={() => setShowDecodeInfo((current) => !current)}
                disabled={!showBoundingBoxes}
              >
                {showDecodeInfo ? "隱藏 BID" : "顯示 BID"}
              </Button>
            </div>
            {isPreviewing && selectedCamera?.sourceScope === "browser" ? (
              <div className="relative overflow-hidden rounded-3xl border bg-card/70 p-3 shadow-sm">
                {isScanningLive ? (
                  <div className="absolute right-5 top-5 z-30 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
                    <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
                    掃描中
                  </div>
                ) : lastScanInfo ? (
                  <div className="absolute right-5 top-5 z-30 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    {lastScanInfo.count > 0 ? `找到 ${lastScanInfo.count} 個` : "未偵測到"} · {lastScanInfo.elapsedMs}ms
                  </div>
                ) : null}
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
                    {showBoundingBoxes && browserFrame && liveOverlaySourceSize
                      ? objects.map((item) => {
                          const bw = Math.max(item.bbox.x2 - item.bbox.x1, 12);
                          const bh = Math.max(item.bbox.y2 - item.bbox.y1, 12);
                          const active = item.bid === selectedBid;
                          const overlayLines = buildOverlayLines(item, showDecodeInfo);

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
                              {overlayLines.length > 0 ? (
                                <span className="absolute -top-2 left-0 max-w-56 -translate-y-full rounded-md bg-background/95 px-2 py-1 text-[10px] font-medium shadow-sm">
                                  {overlayLines.map((line) => (
                                    <span key={line} className="block break-all whitespace-normal leading-tight">
                                      {line}
                                    </span>
                                  ))}
                                </span>
                              ) : null}
                            </button>
                          );
                        })
                      : null}
                  </div>
                </div>
              </div>
            ) : (
              <div className="relative">
                {isPreviewing && selectedCamera?.sourceScope === "backend" && (
                  isScanningLive ? (
                    <div className="absolute right-5 top-5 z-30 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
                      <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
                      掃描中
                    </div>
                  ) : lastScanInfo ? (
                    <div className="absolute right-5 top-5 z-30 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      {stableObjects.length > 0 ? `已鎖定 ${stableObjects.length} 個` : "未偵測到"} · {lastScanInfo.elapsedMs}ms
                    </div>
                  ) : null
                )}
                <DetectionCanvas
                  imageUrl={isPreviewing && selectedCamera?.sourceScope === "backend" ? streamUrl : previewUrl}
                  objects={isPreviewing ? stableObjects : objects}
                  selectedBid={selectedBid}
                  onSelect={setSelectedBid}
                  sourceImageSize={overlaySourceSize}
                  showBoundingBoxes={showBoundingBoxes}
                  showDecodeInfo={showDecodeInfo}
                />
              </div>
            )}
          </SectionCard>

          <SectionCard title="辨識結果列表" description="按下擷取後，當前影格的辨識結果會存入後端資料庫。">
            {(isPreviewing ? stableObjects : objects).length ? (
              <ObjectResultTable items={isPreviewing ? stableObjects : objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
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
    // enumerateDevices() can hang on some browsers/platforms (e.g. Pi Chromium
    // waiting for a permission dialog). Apply a 5-second timeout.
    const devicesPromise = navigator.mediaDevices.enumerateDevices();
    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("enumerateDevices timeout")), 5_000),
    );
    const devices = await Promise.race([devicesPromise, timeoutPromise]);
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