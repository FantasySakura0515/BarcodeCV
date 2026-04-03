"use client";

import Image from "next/image";
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
  viewportClassName,
}: {
  imageUrl: string | null;
  objects: DetectionObject[];
  selectedBid: string | null;
  onSelect?: (bid: string) => void;
  sourceImageSize?: ImageSize | null;
  onImageLoad?: () => void;
  showBoundingBoxes?: boolean;
  showDecodeInfo?: boolean;
  viewportClassName?: string;
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
    <div className={cn("h-full w-full relative flex items-center justify-center bg-transparent", viewportClassName)}>
      <div
        ref={containerRef}
        className="relative h-full w-full overflow-hidden"
      >
        {imageUrl ? (
          <>
            <Image
              src={imageUrl}
              alt="辨識預覽"
              fill
              unoptimized
              sizes="100vw"
              className="absolute inset-0 h-full w-full object-contain"
              onLoad={(event) => {
                setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight });
                onImageLoad?.();
              }}
            />

            {showBoundingBoxes && frame && overlaySourceSize
              ? objects.map((item) => {
                  const active = item.bid === selectedBid;
                  const isDecoded = !!item.barcodeValue;
                  const overlayLines = buildOverlayLines(item, showDecodeInfo);
                  
                  // Coordinate mapping
                  const x = frame.left + (item.bbox.x1 / overlaySourceSize.width) * frame.width;
                  const y = frame.top + (item.bbox.y1 / overlaySourceSize.height) * frame.height;
                  const w = Math.max((item.bbox.x2 - item.bbox.x1) / overlaySourceSize.width * frame.width, 12);
                  const h = Math.max((item.bbox.y2 - item.bbox.y1) / overlaySourceSize.height * frame.height, 12);

                  // Colors based on status and selection
                  let borderColor = isDecoded ? "border-[#00ff66]/70" : "border-[#ef4444]/80";
                  let glowClass = "";
                  let bgClass = "bg-transparent";
                  
                  if (active) {
                    borderColor = "border-[#00f0ff] z-10";
                    glowClass = "shadow-[0_0_15px_#00f0ff,inset_0_0_10px_#00f0ff]";
                    bgClass = "bg-[#00f0ff]/10 backdrop-blur-[1px]";
                  } else if (!isDecoded) {
                    glowClass = "shadow-[0_0_8px_#ef4444]";
                  } else {
                    glowClass = "hover:shadow-[0_0_8px_#00ff66]";
                  }

                  return (
                    <motion.button
                      key={item.bid}
                      initial={{ opacity: 0, scale: 0.98 }}
                      animate={{ opacity: 1, scale: 1 }}
                      type="button"
                      onClick={() => onSelect?.(item.bid)}
                      className={cn(
                        "absolute text-left outline-none transition-all duration-300",
                        borderColor,
                        active ? "border-[2px]" : "border block",
                        glowClass,
                        bgClass
                      )}
                      style={{
                        left: x,
                        top: y,
                        width: w,
                        height: h,
                      }}
                    >
                      {/* Tech Corner Brackets */}
                      <span className={cn("absolute -top-[5px] -left-[5px] w-2.5 h-2.5 border-t-[2px] border-l-[2px]", active ? "border-[#00f0ff]" : isDecoded ? "border-[#00ff66]" : "border-[#ef4444]")} />
                      <span className={cn("absolute -top-[5px] -right-[5px] w-2.5 h-2.5 border-t-[2px] border-r-[2px]", active ? "border-[#00f0ff]" : isDecoded ? "border-[#00ff66]" : "border-[#ef4444]")} />
                      <span className={cn("absolute -bottom-[5px] -left-[5px] w-2.5 h-2.5 border-b-[2px] border-l-[2px]", active ? "border-[#00f0ff]" : isDecoded ? "border-[#00ff66]" : "border-[#ef4444]")} />
                      <span className={cn("absolute -bottom-[5px] -right-[5px] w-2.5 h-2.5 border-b-[2px] border-r-[2px]", active ? "border-[#00f0ff]" : isDecoded ? "border-[#00ff66]" : "border-[#ef4444]")} />

                      {/* Scanning line for undecoded or active elements */}
                      {(active || !isDecoded) && (
                         <span className={cn("absolute top-0 left-0 w-full h-[1px] opacity-70 animate-[scan_2s_ease-in-out_infinite]", active ? "bg-[#00f0ff]" : "bg-[#ef4444]")} />
                      )}

                      {overlayLines.length > 0 ? (
                        <span className={cn(
                          "absolute -top-3 left-1/2 -translate-x-1/2 -translate-y-full min-w-12 max-w-64 truncate whitespace-nowrap px-2 py-0.5 text-[10px] font-mono tracking-widest uppercase border backdrop-blur-md shadow-lg",
                          active ? "bg-[#0b0c10]/90 text-[#00f0ff] border-[#00f0ff]/50" : isDecoded ? "bg-[#0b0c10]/80 text-[#00ff66] border-[#00ff66]/30" : "bg-[#0b0c10]/90 text-[#ef4444] border-[#ef4444]/50"
                        )}>
                          {overlayLines.map((line) => (
                            <span key={line} className="block truncate leading-tight content-center border-b border-white/10 last:border-0 pb-0.5 mb-0.5 last:pb-0 last:mb-0">
                              {line.split("-")[0]}
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
          <div className="flex h-full items-center justify-center font-mono text-[10px] tracking-[0.3em] uppercase text-[#00f0ff]/50 relative z-10 before:absolute before:inset-0 before:bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] before:from-[#00f0ff]/5 before:to-transparent">
            [ WAITING FOR IMAGE FEED ]
          </div>
        )}
      </div>
    </div>
  );
}
