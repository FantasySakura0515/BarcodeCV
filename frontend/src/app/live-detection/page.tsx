"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pulse, ArrowsClockwise, ArrowsIn, ArrowsOut, Camera, CameraRotate, Play, SlidersHorizontal, Stop, WarningCircle, User } from "@phosphor-icons/react";

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
  low:      "low power",
  balanced: "balanced",
  high:     "high performance",
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

function parseApiError(err: unknown, fallbackMessage: string): { message: string; status?: number } {
  if (typeof err !== "object" || err === null) {
    return { message: fallbackMessage };
  }

  const maybeError = err as {
    message?: string;
    response?: {
      status?: number;
      data?: unknown;
    };
  };

  let detail = "";
  const responseData = maybeError.response?.data;
  if (typeof responseData === "string") {
    detail = responseData;
  } else if (responseData && typeof responseData === "object" && "detail" in responseData) {
    const rawDetail = (responseData as { detail?: unknown }).detail;
    if (typeof rawDetail === "string") {
      detail = rawDetail;
    }
  }

  return {
    status: maybeError.response?.status,
    message: detail || maybeError.message || fallbackMessage,
  };
}


async function getBrowserCameras(): Promise<LiveCameraOption[]> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
    return [];
  }
  if (typeof window !== "undefined" && !window.isSecureContext) {
    return [];
  }
  try {
    const devicesPromise = navigator.mediaDevices.enumerateDevices();
    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("enumerateDevices timeout")), 5000)
    );
    const devices = (await Promise.race([devicesPromise, timeoutPromise])) as MediaDeviceInfo[];
    const videoInputs = devices.filter((device) => device.kind === "videoinput");
    return videoInputs.map((device, index) => ({
      id: `browser-${device.deviceId || index}`,
      label: device.label || `Browser Camera ${index + 1}`,
      sourceType: "browser" as CameraInfo["sourceType"],
      sourceScope: "browser" as const,
      deviceId: device.deviceId,
      cameraNum: index,
      width: 1280,
      height: 720,
      available: true,
      status: device.label ? "ready" : "please grant camera access",
    }));
  } catch {
    return [];
  }
}

export default function LiveDetectionPage() {
  const [isSwitchingCamera, setIsSwitchingCamera] = useState(false);
  const [liveResults, setLiveResults] = useState<{ objects: DetectionObject[] }>({ objects: [] });
  const setSelectedObject = (obj: DetectionObject | null) => {
    setSelectedBid(obj?.bid ?? null);
  };
  const handleToggleScan = () => {
    if (isPreviewing) {
      stopPreview();
    } else {
      startPreview();
    }
  };

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
  const [isFullscreen, setIsFullscreen] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoContainerRef = useRef<HTMLDivElement | null>(null);
  const liveDisplayRef = useRef<HTMLDivElement | null>(null);
  const browserStreamRef = useRef<MediaStream | null>(null);
  const browserPreviewUrlRef = useRef<string | null>(null);
  const previewSessionRef = useRef(0);

  const selectedCamera = useMemo(
    () => cameras.find((item) => item.id === selectedCameraId) ?? null,
    [cameras, selectedCameraId],
  );

  const selectedCameraKindLabel = useMemo(() => {
    if (!selectedCamera) {
      return "";
    }
    if (selectedCamera.sourceScope === "backend") {
      if (selectedCamera.id === "main") {
        return "CamArray Main (Aggregated)";
      }
      return `Backend ${selectedCamera.sourceType}`;
    }
    return "Browser Device";
  }, [selectedCamera]);

  const selectedCameraConnection = useMemo(() => {
    if (!selectedCamera) {
      return {
        online: false,
        label: "UNKNOWN",
        detail: "not selected",
        dotClass: "bg-slate-500",
        textClass: "text-slate-500",
      };
    }

    if (selectedCamera.sourceScope === "backend") {
      if (selectedCamera.available) {
        return {
          online: true,
          label: "BACKEND READY",
          detail: selectedCamera.status ?? "backend camera available",
          dotClass: "bg-cyan-400",
          textClass: "text-cyan-400",
        };
      }
      return {
        online: false,
        label: "BACKEND OFFLINE",
        detail: selectedCamera.status ?? "backend camera unavailable",
        dotClass: "bg-red-500",
        textClass: "text-red-500",
      };
    }

    if (browserStream) {
      return {
        online: true,
        label: "BROWSER LIVE",
        detail: "streaming browser device camera",
        dotClass: "bg-emerald-400",
        textClass: "text-emerald-400",
      };
    }

    return {
      online: true,
      label: "BROWSER READY",
      detail: selectedCamera.status ?? "waiting to start preview or browser permission",
      dotClass: "bg-cyan-400",
      textClass: "text-cyan-400",
    };
  }, [browserStream, selectedCamera]);

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

  const refreshCameras = useCallback(async () => {
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
        const msg = backendResult.reason instanceof Error ? backendResult.reason.message : "cannot connect to backend";
        setError(`backend camera load failed: ${msg}`);
      } else if (!Array.isArray(rawBackend)) {
        setError(`unexpected backend response format (not an array): ${JSON.stringify(rawBackend)?.slice(0, 120)}`);
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
      const message = err instanceof Error ? err.message : "failed to get camera list";
      setError(message);
    } finally {
      setIsLoadingCameras(false);
    }
  }, [selectedCameraId]);

  const previewFromBrowserCamera = useCallback(async () => {
    if (!selectedCamera) {
      throw new Error("please select an available camera");
    }

    const snapshot = await captureBrowserSnapshot(
      selectedCamera,
      performanceProfile.jpegQuality,
      scaleDimension(videoRef.current?.videoWidth || 1280, performanceProfile.detectScale),
    );
    return previewDetection(snapshot.file);
  }, [performanceProfile.detectScale, performanceProfile.jpegQuality, selectedCamera]);

  useEffect(() => {
    void refreshCameras();
  }, [refreshCameras]);

  useEffect(() => {
    return () => {
      stopBrowserStream();
      clearBrowserPreviewUrl();
    };
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === liveDisplayRef.current);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
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
          if (selectedCamera.sourceScope === "backend") {
            const response = await fetchLiveCameraDetection(
              selectedCameraId,
              "opencv",
              performanceTargetSize?.detect.width ?? scaleDimension(selectedCamera?.width ?? 0, performanceProfile.detectScale),
            );
            if (!cancelled && previewSessionRef.current === sessionId) {
              const elapsedMs = Date.now() - cycleStart;
              syncCameraActualResolution(selectedCameraId, response.sourceImage);
              setObjects(response.objects); setLiveResults({ objects: response.objects });
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
              setObjects(response.objects); setLiveResults({ objects: response.objects });
              setStableObjects((prev) => mergeStableObjects(prev, response.objects));
              setOverlaySourceSize(response.sourceImage ?? null);
              setSelectedBid((current) => current ?? response.objects[0]?.bid ?? null);
              setLastScanInfo({ count: response.objects.length, elapsedMs, at: new Date() });
              setError(null);
            }
          }
        } catch (err) {
          if (!cancelled && previewSessionRef.current === sessionId) {
            const { message, status } = parseApiError(err, "live detection failed");
            setError(message);

            if (selectedCamera.sourceScope === "backend" && (status === 404 || status === 503)) {
              // Camera is currently unavailable; stop loop to avoid endless 503 spam.
              cancelled = true;
              setIsPreviewing(false);
              break;
            }
          }
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
    };
  }, [isPreviewing, performanceProfile.minCycleMs, performanceProfile.detectScale, performanceTargetSize, previewFromBrowserCamera, selectedCamera, selectedCameraId]);

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

  function startPreview() {
    if (!selectedCameraId || !selectedCamera) {
      setError("please select an available camera");
      return;
    }

    if (selectedCamera.sourceScope === "backend" && !selectedCamera.available) {
      setError(`camera is currently unavailable: ${selectedCamera.status ?? "check camera connection and dependencies"}`);
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
        setObjects(response.objects); setLiveResults({ objects: response.objects });
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
        setObjects(response.objects); setLiveResults({ objects: response.objects });
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
  const previewViewportClassName = isFullscreen ? "h-[calc(100dvh-10rem)] min-h-[28rem]" : undefined;

  async function toggleFullscreen() {
    const element = liveDisplayRef.current;
    if (!element) {
      return;
    }

    if (document.fullscreenElement === element) {
      await document.exitFullscreen();
      return;
    }

    await element.requestFullscreen();
  }

  return (
    <div className="flex flex-col min-h-screen bg-black text-slate-300 font-sans selection:bg-cyan-900 selection:text-cyan-100">
      <PageHeader
        title="即時掃描"
        description="Live Detection View"
        action={
          <div className="flex items-center gap-3">
            <Select value={selectedCameraId} onValueChange={handleCameraChange}>
              <SelectTrigger className="w-[220px] bg-black/50 border-cyan-900/50 text-cyan-100">
                {isLoadingCameras ? (
                  <div className="flex items-center gap-2">
                    <ArrowsClockwise className="h-4 w-4 animate-spin" />
                    載入中...
                  </div>
                ) : (
                  <SelectValue placeholder="選擇鏡頭" />
                )}
              </SelectTrigger>
              <SelectContent className="bg-[#0b0c10] border-cyan-900/50 text-slate-300">
                {cameras.map((camera) => (
                  <SelectItem
                    key={camera.id}
                    value={camera.id}
                    disabled={camera.sourceScope === "backend" && !camera.available}
                    className="focus:bg-cyan-950 focus:text-cyan-100"
                  >
                    <div className="flex items-center gap-2">
                      {camera.sourceScope === "browser" ? <User size={14} /> : <Camera size={14} />}
                      <span>{camera.label}</span>
                      {camera.sourceScope === "backend" && camera.id === "main" ? (
                        <Badge variant="outline" className="ml-1 text-[10px] border-cyan-800/60 text-cyan-300">
                          CamArray
                        </Badge>
                      ) : null}
                      {!camera.available && <Badge variant="outline" className="ml-2 text-[10px] border-red-900/50 text-red-500">外部占用</Badge>}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              onClick={handleToggleScan}
              disabled={isSwitchingCamera || !selectedCameraId}
              variant={isPreviewing ? "destructive" : "default"}
              size="sm"
              className={
                isPreviewing
                  ? "bg-red-900/40 text-red-400 hover:bg-red-900/60 border border-red-800/50 uppercase tracking-wider font-semibold"
                  : "bg-cyan-900/40 text-cyan-400 hover:bg-cyan-900/60 border border-cyan-800/50 uppercase tracking-wider font-semibold shadow-[0_0_15px_rgba(6,182,212,0.15)]"
              }
            >
              {isSwitchingCamera ? (
                <>
                  <ArrowsClockwise className="mr-2 h-4 w-4 animate-spin" />
                  切換中
                </>
              ) : isPreviewing ? (
                <>
                  <Stop className="mr-2 h-4 w-4" />
                  停止掃描
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  開始掃描
                </>
              )}
            </Button>
          </div>
        }
      />

      <main className="flex-1 p-6 z-10 relative">
        <div className="mx-auto max-w-7xl space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 flex flex-col gap-6">
              <div
                className="group relative overflow-hidden rounded-xl border border-cyan-900/30 bg-black/40 shadow-[0_0_30px_rgba(6,182,212,0.03)] transition-all duration-300 hover:border-cyan-700/50 hover:shadow-[0_0_40px_rgba(6,182,212,0.06)] ring-1 ring-white/5"
                style={{
                  backgroundImage:
                    "radial-gradient(ellipse at top, rgba(6, 182, 212, 0.05), transparent 70%)",
                }}
              >
                <div className="border-b border-cyan-900/30 bg-black/40 px-4 py-3 relative overflow-hidden flex justify-between items-center">
                  <div className="absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-cyan-500/20 to-transparent"></div>
                  <div className="flex items-center gap-3">
                    <Camera className="h-4 w-4 text-cyan-500" />
                    <h2 className="text-sm font-semibold tracking-wide text-cyan-100 uppercase">
                      鏡頭畫面
                    </h2>
                  </div>
                  {isPreviewing && (
                    <div className="flex items-center gap-2">
                        <span className="relative flex h-2 w-2">
                           <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                           <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                        </span>
                        <span className="text-xs font-medium text-red-400 uppercase tracking-widest">LIVE</span>
                    </div>
                  )}
                </div>
                <div className="relative aspect-video w-full bg-[#050505] overflow-hidden flex items-center justify-center min-h-100">
                  <div ref={videoContainerRef} className="relative aspect-video w-full overflow-hidden min-h-100 border border-cyan-800/10 rounded-lg">
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
                    {showBoundingBoxes && browserFrame && liveOverlaySourceSize && objects ? objects.map((item) => {
                      const bw = Math.max(item.bbox.x2 - item.bbox.x1, 12);
                      const bh = Math.max(item.bbox.y2 - item.bbox.y1, 12);
                      const active = item.bid === selectedObject?.bid;
                      const overlayLines = buildOverlayLines(item, showDecodeInfo);

                      return (
                        <button
                          key={item.bid}
                          type="button"
                          onClick={() => setSelectedObject(item)}
                          className={`pointer-events-auto absolute rounded-xl border-2 text-left outline-none transition-all ${
                            active
                              ? "border-cyan-400 shadow-[0_0_0_9999px_rgba(6,182,212,0.12)] bg-cyan-400/10 z-30"
                              : "border-cyan-500/90 hover:border-cyan-300 bg-cyan-500/10 z-20"
                          }`}
                          style={{
                            left: browserFrame.left + (item.bbox.x1 / liveOverlaySourceSize.width) * browserFrame.width,
                            top: browserFrame.top + (item.bbox.y1 / liveOverlaySourceSize.height) * browserFrame.height,
                            width: (bw / liveOverlaySourceSize.width) * browserFrame.width,
                            height: (bh / liveOverlaySourceSize.height) * browserFrame.height,
                          }}
                        >
                          {overlayLines.length > 0 ? (
                            <span className="absolute -top-2 left-0 min-w-16 max-w-72 -translate-y-full truncate whitespace-nowrap rounded border border-cyan-500/50 bg-black/90 px-2.5 py-1 text-[10px] font-mono shadow-[0_0_10px_rgba(6,182,212,0.2)] text-cyan-300">
                              {overlayLines.map((line) => (
                                <span key={line} className="block truncate leading-tight">
                                  {line}
                                </span>
                              ))}
                            </span>
                          ) : null}
                        </button>
                      );
                    }) : null}
                  </div>
                </div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-4 flex flex-col gap-6">
              {selectedCamera && (
                <div className="overflow-hidden rounded-xl border border-cyan-900/30 bg-black/40 p-5 shadow-[0_0_30px_rgba(6,182,212,0.03)] ring-1 ring-white/5 relative group">
                  <div className="absolute inset-0 bg-linear-to-br from-cyan-950/10 via-transparent to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"></div>

                  <div className="flex items-center justify-between mb-4 relative z-10">
                    <div className="flex items-center gap-2">
                      <SlidersHorizontal className="h-4 w-4 text-cyan-500" />
                      <h3 className="text-sm font-semibold text-cyan-100 uppercase tracking-wider">
                        鏡頭資訊
                      </h3>
                    </div>
                  </div>

                  <div className="space-y-4 relative z-10">
                    <div className="rounded-lg border border-cyan-900/20 bg-black/50 p-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-cyan-700/80 mb-1">
                        選擇的鏡頭
                      </p>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-cyan-50">
                          {selectedCamera?.label || selectedCameraId}
                        </p>
                        {selectedCamera?.sourceScope === "backend" && selectedCamera.id === "main" ? (
                          <Badge variant="outline" className="text-[10px] border-cyan-800/60 text-cyan-300">
                            CamArray
                          </Badge>
                        ) : null}
                      </div>
                    </div>

                    <div className="rounded-lg border border-cyan-900/20 bg-black/50 p-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-cyan-700/80 mb-1">
                        鏡頭類型
                      </p>
                      <p className="text-xs font-medium text-cyan-200">{selectedCameraKindLabel}</p>
                    </div>

                    <div className="rounded-lg border border-cyan-900/20 bg-black/50 p-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-cyan-700/80 mb-1">
                        解析度
                      </p>
                      <p className="text-xs font-medium text-cyan-200">
                        {selectedCameraSurface?.width && selectedCameraSurface.height
                          ? `${selectedCameraSurface.width} x ${selectedCameraSurface.height}`
                          : `${selectedCamera.width} x ${selectedCamera.height}`}
                      </p>
                    </div>

                    <div className="rounded-lg border border-cyan-900/20 bg-black/50 p-3 flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-medium uppercase tracking-wide text-cyan-700/80">連線狀態</p>
                        <p className="mt-1 text-[11px] leading-relaxed text-slate-400 break-words">
                          {selectedCameraConnection.detail}
                        </p>
                      </div>
                       <span className={`shrink-0 flex items-center gap-1.5 text-xs font-medium ${selectedCameraConnection.textClass}`}>
                          <span className={`inline-block h-1.5 w-1.5 rounded-full ${selectedCameraConnection.dotClass}`}></span>
                          {selectedCameraConnection.label}
                       </span>
                    </div>
                  </div>
                </div>
              )}
               <div className="overflow-hidden rounded-xl border border-cyan-900/30 bg-black/40 p-5 shadow-[0_0_30px_rgba(6,182,212,0.03)] ring-1 ring-white/5 relative group">
                   <div className="absolute inset-0 bg-linear-to-br from-cyan-950/10 via-transparent to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"></div>

                   <div className="flex items-center justify-between mb-4 relative z-10">
                    <div className="flex items-center gap-2">
                      <Pulse className="h-4 w-4 text-cyan-500" />
                      <h3 className="text-sm font-semibold text-cyan-100 uppercase tracking-wider">
                        掃描狀態
                      </h3>
                    </div>
                  </div>
                   <div className="space-y-4 relative z-10">
                    <div className="rounded-lg border border-cyan-900/20 bg-black/50 p-3 flex items-center justify-between">
                       <p className="text-xs font-medium uppercase tracking-wide text-cyan-700/80">目前狀態</p>
                         {isPreviewing ? (
                           <span className="flex items-center gap-1.5 text-xs font-bold text-red-500 tracking-wider">
                                <span className="inline-block h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse"></span>
                                SCANNING
                           </span>
                       ) : (
                           <span className="flex items-center gap-1.5 text-xs font-medium text-slate-500 tracking-wider">
                                <span className="inline-block h-1.5 w-1.5 rounded-full bg-slate-500"></span>
                                IDLE
                           </span>
                       )}
                    </div>
                    {isPreviewing && (
                        <div className="rounded-lg border border-cyan-900/20 bg-black/50 p-3">
                            <p className="text-xs font-medium uppercase tracking-wide text-cyan-700/80 mb-2">更新頻率</p>
                            <div className="flex items-center gap-3">
                                <div className="h-1.5 flex-1 bg-black rounded-full overflow-hidden">
                                     <div className="h-full bg-cyan-500/50 w-full animate-[pulse_1s_ease-in-out_infinite]"></div>
                                </div>
                                <span className="text-[10px] text-cyan-500/70 font-mono">15fps (est)</span>
                            </div>
                        </div>
                    )}
                   </div>
               </div>
            </div>
          </div>

          <div className="w-full mt-8">
             <ObjectResultTable items={objects} selectedBid={selectedBid} onSelect={(bid) => setSelectedBid(bid)} />
          </div>
        </div>
      </main>
    </div>
  );
}
