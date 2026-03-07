"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import type { DetectionObject, ImageSize } from "@/types";

interface Size {
  width: number;
  height: number;
}

export function DetectionCanvas({
  imageUrl,
  objects,
  selectedBid,
  onSelect,
  sourceImageSize,
}: {
  imageUrl: string | null;
  objects: DetectionObject[];
  selectedBid: string | null;
  onSelect?: (bid: string) => void;
  sourceImageSize?: ImageSize | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState<Size>({ width: 0, height: 0 });
  const [imageSize, setImageSize] = useState<Size | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }

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
    if (!imageSize || !containerSize.width || !containerSize.height) {
      return null;
    }

    const containerRatio = containerSize.width / containerSize.height;
    const imageRatio = imageSize.width / imageSize.height;

    if (containerRatio > imageRatio) {
      const height = containerSize.height;
      const width = height * imageRatio;
      return {
        width,
        height,
        left: (containerSize.width - width) / 2,
        top: 0,
      };
    }

    const width = containerSize.width;
    const height = width / imageRatio;
    return {
      width,
      height,
      left: 0,
      top: (containerSize.height - height) / 2,
    };
  }, [containerSize, imageSize]);

  const overlaySourceSize = sourceImageSize?.width && sourceImageSize?.height
    ? sourceImageSize
    : imageSize;

  return (
    <div className="relative overflow-hidden rounded-3xl border bg-card/70 p-3 shadow-sm">
      <div
        ref={containerRef}
        className="relative h-[min(62vh,40rem)] min-h-80 overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#f8fafc,#dbeafe)] dark:bg-[linear-gradient(135deg,#0f172a,#1e293b)]"
      >
        {imageUrl ? (
          <>
            <img
              src={imageUrl}
              alt="Detection preview"
              className="absolute inset-0 h-full w-full object-contain"
              onLoad={(event) => {
                setImageSize({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                });
              }}
            />

            {frame && overlaySourceSize
              ? objects.map((item) => {
                  const width = Math.max(item.bbox.x2 - item.bbox.x1, 12);
                  const height = Math.max(item.bbox.y2 - item.bbox.y1, 12);
                  const active = item.bid === selectedBid;

                  return (
                    <motion.button
                      key={item.bid}
                      initial={{ opacity: 0, scale: 0.96 }}
                      animate={{ opacity: 1, scale: 1 }}
                      type="button"
                      onClick={() => onSelect?.(item.bid)}
                      className={cn(
                        "absolute rounded-xl border-2 text-left outline-none transition-all",
                        active
                          ? "border-sky-400 shadow-[0_0_0_9999px_rgba(15,23,42,0.12)]"
                          : "border-emerald-400/90 hover:border-emerald-300",
                      )}
                      style={{
                        left: frame.left + (item.bbox.x1 / overlaySourceSize.width) * frame.width,
                        top: frame.top + (item.bbox.y1 / overlaySourceSize.height) * frame.height,
                        width: (width / overlaySourceSize.width) * frame.width,
                        height: (height / overlaySourceSize.height) * frame.height,
                      }}
                    >
                      <span className="absolute -top-7 left-0 max-w-40 truncate rounded-full bg-background/95 px-2 py-1 text-[10px] font-medium shadow-sm">
                        {item.bid}
                      </span>
                    </motion.button>
                  );
                })
              : null}
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            請先上傳圖片開始辨識
          </div>
        )}
      </div>
    </div>
  );
}
