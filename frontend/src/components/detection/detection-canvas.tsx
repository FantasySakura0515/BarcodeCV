"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import type { DetectionObject, ImageSize } from "@/types";

interface Size {
  width: number;
  height: number;
}

function buildOverlayLines(item: DetectionObject, showDecodeInfo: boolean) {
  if (!showDecodeInfo) {
    return [];
  }

  return [item.bid];
}

export function DetectionCanvas({
  imageUrl,
  objects,
  selectedBid,
  onSelect,
  sourceImageSize,
  onImageLoad,
  showBoundingBoxes = true,
  showDecodeInfo = false,
}: {
  imageUrl: string | null;
  objects: DetectionObject[];
  selectedBid: string | null;
  onSelect?: (bid: string) => void;
  sourceImageSize?: ImageSize | null;
  onImageLoad?: () => void;
  showBoundingBoxes?: boolean;
  showDecodeInfo?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState<Size>({ width: 0, height: 0 });
  const [imageSize, setImageSize] = useState<Size | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const updateSize = () => {
      const rect = element.getBoundingClientRect();
      setContainerSize({ width: rect.width, height: rect.height });
    };

    updateSize();

    const observer = new ResizeObserver(updateSize);
    observer.observe(element);

    return () => observer.disconnect();
  }, []);

  const frame = useMemo(() => {
    if (!imageSize || !containerSize.width || !containerSize.height) return null;

    const containerRatio = containerSize.width / containerSize.height;
    const imageRatio = imageSize.width / imageSize.height;

    if (containerRatio > imageRatio) {
      const height = containerSize.height;
      const width = height * imageRatio;
      return { width, height, left: (containerSize.width - width) / 2, top: 0 };
    }

    const width = containerSize.width;
    const height = width / imageRatio;
    return { width, height, left: 0, top: (containerSize.height - height) / 2 };
  }, [containerSize, imageSize]);

  const overlaySourceSize = sourceImageSize?.width && sourceImageSize?.height ? sourceImageSize : imageSize;

  return (
    <div className="relative overflow-hidden rounded-xl border bg-card p-3 shadow-sm">
      <div ref={containerRef} className="relative h-[min(62vh,40rem)] min-h-80 overflow-hidden rounded-lg bg-muted/40">
        {imageUrl ? (
          <>
            <img
              src={imageUrl}
              alt="辨識預覽"
              className="absolute inset-0 h-full w-full object-contain"
              onLoad={(event) => {
                setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight });
                onImageLoad?.();
              }}
            />

            {showBoundingBoxes && frame && overlaySourceSize
              ? objects.map((item) => {
                  const width = Math.max(item.bbox.x2 - item.bbox.x1, 12);
                  const height = Math.max(item.bbox.y2 - item.bbox.y1, 12);
                  const active = item.bid === selectedBid;
                  const overlayLines = buildOverlayLines(item, showDecodeInfo);

                  return (
                    <motion.button
                      key={item.bid}
                      initial={{ opacity: 0, scale: 0.98 }}
                      animate={{ opacity: 1, scale: 1 }}
                      type="button"
                      onClick={() => onSelect?.(item.bid)}
                      className={cn(
                        "absolute rounded-md border-2 text-left outline-none transition-all",
                        active ? "border-sky-500 shadow-[0_0_0_9999px_rgba(15,23,42,0.10)]" : "border-emerald-500/90 hover:border-emerald-400",
                      )}
                      style={{
                        left: frame.left + (item.bbox.x1 / overlaySourceSize.width) * frame.width,
                        top: frame.top + (item.bbox.y1 / overlaySourceSize.height) * frame.height,
                        width: (width / overlaySourceSize.width) * frame.width,
                        height: (height / overlaySourceSize.height) * frame.height,
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
                    </motion.button>
                  );
                })
              : null}
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">尚未載入影像。請先上傳或擷取影像後開始。</div>
        )}
      </div>
    </div>
  );
}
