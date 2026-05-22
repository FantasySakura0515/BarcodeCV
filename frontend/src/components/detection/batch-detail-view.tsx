"use client";

import { useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ModelBadge } from "@/components/common/model-badge";
import { SectionCard } from "@/components/common/section-card";
import { DetectionCanvas } from "@/components/detection/detection-canvas";
import { ObjectResultTable } from "@/components/detection/object-result-table";
import { Button } from "@/components/ui/button";
import type { DetectionBatch } from "@/types";

export function BatchDetailView({ batch }: { batch: DetectionBatch }) {
  const [selectedBid, setSelectedBid] = useState<string | null>(batch.objects[0]?.bid ?? null);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [showDecodeInfo, setShowDecodeInfo] = useState(false);
  const previewImageUrl = batch.objects[0]?.imagePath ?? null;

  return (
    <>
      <section className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <SectionCard
          title="影像預覽"
          description="可切換是否顯示物件框與 BID。"
          action={
            <div className="flex flex-wrap gap-2">
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
          }
        >
          <DetectionCanvas
            imageUrl={previewImageUrl}
            objects={batch.objects}
            selectedBid={selectedBid}
            onSelect={setSelectedBid}
            showBoundingBoxes={showBoundingBoxes}
            showDecodeInfo={showDecodeInfo}
          />
        </SectionCard>

        <SectionCard title="批次摘要" description="條碼與 OCR 輸出摘要及模型來源。">
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>批次 ID（RID）</span><span className="font-medium">{batch.rid}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>物件數</span><span className="font-medium">{batch.objectCount}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>條碼成功數</span><span className="font-medium">{batch.barcodeSuccessCount}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>模型</span><ModelBadge model={batch.model} /></div>
          </div>
        </SectionCard>
      </section>

      <SectionCard title="已偵測物件" description="此批次中偵測到的所有物件。">
        {batch.objects.length ? (
          <ObjectResultTable items={batch.objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
        ) : (
          <EmptyState title="此批次沒有物件" description="此批次不包含物件層級結果。" />
        )}
      </SectionCard>
    </>
  );
}
