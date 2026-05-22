"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Dynamsoft BarcodeScanner wrapper for Next.js.
 *
 * Loads the SDK from /dynamsoft/dbr.bundle.js (self-hosted in public/),
 * creates a BarcodeScanner instance that manages its own camera feed + WASM
 * decoding, and reports results via the `onResults` callback.
 */

export interface DynamsoftResult {
  text: string;
  formatString: string;
  confidence: number;
  location: {
    points: Array<{ x: number; y: number }>;
  };
}

interface DynamsoftScannerProps {
  /** Called whenever a *new unique* barcode is scanned. */
  onResult?: (result: DynamsoftResult) => void;
  /** Called with all accumulated unique results whenever the set changes. */
  onResults?: (results: DynamsoftResult[]) => void;
  /** Called when the scanner encounters an error. */
  onError?: (error: string) => void;
  /** License key. Defaults to public trial. */
  license?: string;
  /** Template file path relative to public/dynamsoft/. */
  templateFilePath?: string;
  /** Height of the scanner container. */
  height?: string;
}

// Track global script loading state
let scriptLoadPromise: Promise<void> | null = null;
const templateWarmupPromises = new Map<string, Promise<void>>();

interface DynamsoftBarcodeScannerCtor {
  new (options: Record<string, unknown>): DynamsoftBarcodeScannerInstance;
}

interface DynamsoftBarcodeScannerInstance {
  launch(): Promise<void>;
  dispose(): void;
}

interface DynamsoftGlobal {
  BarcodeScanner?: DynamsoftBarcodeScannerCtor;
  Core?: {
    CoreModule?: {
      engineResourcePaths?: Record<string, unknown>;
      wasmLoadOptions?: Record<string, unknown>;
      loadWasm?: () => Promise<void>;
    };
  };
  DCE?: {
    CameraView?: {
      defaultUIElementURL?: string;
    };
  };
}

interface BarcodeScannerResultLike {
  text?: string;
  formatString?: string;
  confidence?: number;
  location?: {
    points?: Array<{ x: number; y: number }>;
  };
}

function preloadAsset(href: string, as: "script" | "fetch", crossOrigin?: "anonymous") {
  if (typeof document === "undefined") {
    return;
  }

  const selector = `link[rel="preload"][href="${href}"]`;
  if (document.head.querySelector(selector)) {
    return;
  }

  const link = document.createElement("link");
  link.rel = "preload";
  link.href = href;
  link.as = as;
  if (crossOrigin) {
    link.crossOrigin = crossOrigin;
  }
  document.head.appendChild(link);
}

function warmupTemplate(templateFilePath: string): Promise<void> {
  const existing = templateWarmupPromises.get(templateFilePath);
  if (existing) {
    return existing;
  }

  const promise = fetch(templateFilePath, { cache: "force-cache" })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to preload template: ${templateFilePath}`);
      }
    })
    .catch((error) => {
      templateWarmupPromises.delete(templateFilePath);
      throw error;
    });

  templateWarmupPromises.set(templateFilePath, promise);
  return promise;
}

export function warmupDynamsoftResources(templateFilePath = "/dynamsoft/ReadDataMatrix.json") {
  preloadAsset("/dynamsoft/dbr.bundle.js", "script");
  preloadAsset("/dynamsoft/dynamsoft-barcode-reader-bundle.wasm", "fetch", "anonymous");
  preloadAsset("/dynamsoft/dynamsoft-barcode-reader-bundle-ml-simd.js", "fetch", "anonymous");
  preloadAsset("/dynamsoft/dynamsoft-barcode-reader-bundle-ml-simd.wasm", "fetch", "anonymous");
  preloadAsset("/dynamsoft/dynamsoft-barcode-reader-bundle-ml-simd-pthread.js", "fetch", "anonymous");
  preloadAsset("/dynamsoft/dynamsoft-barcode-reader-bundle-ml-simd-pthread.wasm", "fetch", "anonymous");
  preloadAsset("/dynamsoft/dynamsoft-barcode-reader-bundle-ml-simd-pthread.worker.js", "fetch", "anonymous");
  preloadAsset("/dynamsoft/ui/dce.ui.xml", "fetch", "anonymous");
  preloadAsset(templateFilePath, "fetch", "anonymous");

  return loadDynamsoftScript()
    .then(async () => {
      const Dynamsoft = (window as Window & { Dynamsoft?: DynamsoftGlobal }).Dynamsoft;
      if (Dynamsoft?.Core?.CoreModule) {
        Dynamsoft.Core.CoreModule.engineResourcePaths = {
          rootDirectory: "/dynamsoft/",
          dbrBundle: "/dynamsoft/",
          dce: "/dynamsoft/",
          std: "/dynamsoft/",
        };
        Dynamsoft.Core.CoreModule.wasmLoadOptions = {
          wasmType: "ml-simd",
        };
      }
      if (Dynamsoft?.DCE?.CameraView) {
        Dynamsoft.DCE.CameraView.defaultUIElementURL = "/dynamsoft/ui/dce.ui.xml";
      }

      await Promise.allSettled([
        warmupTemplate(templateFilePath),
        Dynamsoft?.Core?.CoreModule?.loadWasm?.() ?? Promise.resolve(),
      ]);
    })
    .then(() => undefined);
}

function loadDynamsoftScript(): Promise<void> {
  if (scriptLoadPromise) return scriptLoadPromise;

  scriptLoadPromise = new Promise((resolve, reject) => {
    // Already loaded?
  if (typeof window !== "undefined" && (window as Window & { Dynamsoft?: DynamsoftGlobal }).Dynamsoft?.BarcodeScanner) {
      resolve();
      return;
    }

    const script = document.createElement("script");
    script.src = "/dynamsoft/dbr.bundle.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptLoadPromise = null;
      reject(new Error("Failed to load Dynamsoft SDK"));
    };
    document.head.appendChild(script);
  });

  return scriptLoadPromise;
}

export function DynamsoftScanner({
  onResult,
  onResults,
  onError,
  license = "DLS2eyJvcmdhbml6YXRpb25JRCI6IjIwMDAwMSJ9",
  templateFilePath = "/dynamsoft/ReadDataMatrix.json",
  height = "min(62vh, 40rem)",
}: DynamsoftScannerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scannerRef = useRef<DynamsoftBarcodeScannerInstance | null>(null);
  const resultsRef = useRef<DynamsoftResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const onResultRef = useRef(onResult);
  const onResultsRef = useRef(onResults);
  const onErrorRef = useRef(onError);
  onResultRef.current = onResult;
  onResultsRef.current = onResults;
  onErrorRef.current = onError;

  const initScanner = useCallback(async () => {
    if (!containerRef.current) return;

    try {
      const initStartedAt = performance.now();
      setIsLoading(true);
      setError(null);

  await warmupDynamsoftResources(templateFilePath);

  const Dynamsoft = (window as Window & { Dynamsoft?: DynamsoftGlobal }).Dynamsoft;
      if (!Dynamsoft?.BarcodeScanner) {
        throw new Error("Dynamsoft BarcodeScanner not available after script load");
      }

      // Dispose previous instance if any
      if (scannerRef.current) {
        try { scannerRef.current.dispose(); } catch { /* ignore */ }
        scannerRef.current = null;
      }

      // Clear container
      containerRef.current.innerHTML = "";
      resultsRef.current = [];

      const scanner = new Dynamsoft.BarcodeScanner({
        license,
        container: containerRef.current,
        templateFilePath,
        utilizedTemplateNames: {
          single: "ReadDataMatrix",
          multi_unique: "ReadDataMatrix",
          image: "ReadDataMatrix_ReadRate",
        },
        engineResourcePaths: {
          rootDirectory: "/dynamsoft/",
          dbrBundle: "/dynamsoft/",
          dce: "/dynamsoft/",
          std: "/dynamsoft/",
        },
        scanMode: 1, // SM_MULTI_UNIQUE
        showResultView: false,
        showUploadImageButton: false,
        showPoweredByDynamsoft: false,
        duplicateForgetTime: 5000,
        scannerViewConfig: {
          showCloseButton: false,
          showFlashButton: true,
        },
  onUniqueBarcodeScanned: (result: BarcodeScannerResultLike) => {
          const mapped: DynamsoftResult = {
            text: result.text ?? "",
            formatString: result.formatString ?? "",
            confidence: result.confidence ?? 0,
            location: { points: result.location?.points ?? [] },
          };
          resultsRef.current = [...resultsRef.current, mapped];
          onResultRef.current?.(mapped);
          onResultsRef.current?.([...resultsRef.current]);
        },
        onInitReady: () => {
          console.info("[Dynamsoft] scanner init ready in", Math.round(performance.now() - initStartedAt), "ms");
          setIsLoading(false);
        },
      });

      scannerRef.current = scanner;

      // launch() resolves when the user closes the scanner or it finishes in SM_SINGLE mode.
      // In SM_MULTI_UNIQUE it stays open until dispose().
      scanner.launch().catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        if (!msg.includes("disposed")) {
          setError(msg);
          onErrorRef.current?.(msg);
        }
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Dynamsoft 初始化失敗";
      setError(message);
      onErrorRef.current?.(message);
      setIsLoading(false);
    }
  }, [license, templateFilePath]);

  useEffect(() => {
    void initScanner();

    return () => {
      if (scannerRef.current) {
        try { scannerRef.current.dispose(); } catch { /* ignore */ }
        scannerRef.current = null;
      }
    };
  }, [initScanner]);

  return (
    <div className="relative overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#f8fafc,#dbeafe)] dark:bg-[linear-gradient(135deg,#0f172a,#1e293b)]">
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted-foreground/30 border-t-sky-500" />
            <p className="text-sm text-muted-foreground">正在載入 Dynamsoft 掃描引擎…</p>
          </div>
        </div>
      )}
      {error && (
        <div className="absolute inset-x-0 top-0 z-20 bg-destructive/90 px-4 py-2 text-center text-sm text-white">
          {error}
        </div>
      )}
      <div
        ref={containerRef}
        style={{ height, minHeight: "20rem", width: "100%" }}
      />
    </div>
  );
}
