"use client";

import { useState } from "react";
import { DownloadSimple, Play, Trash } from "@phosphor-icons/react";
import { motion } from "framer-motion";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { DetectionCanvas } from "@/components/detection/detection-canvas";
import { ObjectResultTable } from "@/components/detection/object-result-table";
import { UploadDropzone } from "@/components/detection/upload-dropzone";
import { Button } from "@/components/ui/button";
import { useDetectionStore } from "@/stores/use-detection-store";

export default function DetectionPage() {
  const { imageFile, imageUrl, rid, objects, selectedBid, isLoading, error, setImageFile, setSelectedBid, clear, submitDetection } =
    useDetectionStore();
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [showDecodeInfo, setShowDecodeInfo] = useState(false);

  const selectedObject = objects.find((item) => item.bid === selectedBid) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        badge="影像流程"
        title="影像辨識"
        description="上傳單張影像，執行後端辨識，並檢視物件層級的條碼與 OCR 結果。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => submitDetection()} disabled={!imageFile || isLoading}>
              <Play size={16} />
              {isLoading ? "執行中..." : "執行辨識"}
            </Button>
            <Button variant="outline" onClick={clear}>
              <Trash size={16} />
              清除
            </Button>
          </div>
        }
      />

      <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <div className="space-y-6">
          <UploadDropzone onFileSelect={setImageFile} fileName={imageFile?.name} />

          <SectionCard title="批次摘要" description="目前批次狀態與所選物件資訊。">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
                <span className="text-muted-foreground">批次 ID（RID）</span>
                <span className="font-medium">{rid ?? "尚未開始"}</span>
              </div>
              <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
                <span className="text-muted-foreground">偵測物件數</span>
                <span className="font-medium">{objects.length}</span>
              </div>
              <div className="rounded-xl border bg-background p-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">目前選取物件</p>
                {selectedObject ? (
                  <div className="space-y-2">
                    <p className="break-all font-mono text-sm font-semibold">{selectedObject.bid}</p>
                    <p className="break-all text-sm text-muted-foreground">條碼：{selectedObject.barcodeValue ?? "未偵測到"}</p>
                    <p className="wrap-break-word text-sm text-muted-foreground">OCR：{selectedObject.ocrText ?? "無"}</p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">尚未選取物件。</p>
                )}
              </div>
              {error ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3">
                  <p className="text-sm text-destructive">{error}</p>
                  <Button size="sm" variant="outline" className="mt-2" onClick={() => submitDetection()} disabled={!imageFile || isLoading}>
                    重試
                  </Button>
                </div>
              ) : null}
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <SectionCard
              title="辨識影像"
              description="可切換是否顯示物件框與解碼資訊，方便比對原圖。"
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
                imageUrl={imageUrl}
                objects={objects}
                selectedBid={selectedBid}
                onSelect={setSelectedBid}
                showBoundingBoxes={showBoundingBoxes}
                showDecodeInfo={showDecodeInfo}
              />
            </SectionCard>
          </motion.div>

          <SectionCard
            title="辨識結果"
            description="物件清單與方框選取會保持同步。"
            action={
              <Button variant="outline" disabled={!objects.length}>
                <DownloadSimple size={16} />
                匯出
              </Button>
            }
          >
            {objects.length ? (
              <ObjectResultTable items={objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
            ) : (
              <EmptyState title="尚無辨識結果" description="請先上傳影像並執行辨識，即可查看物件層級結果。" />
            )}
          </SectionCard>
        </div>
      </section>
    </div>
  );
}
