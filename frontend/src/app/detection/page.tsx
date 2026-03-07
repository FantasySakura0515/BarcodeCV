"use client";

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
  const {
    imageFile,
    imageUrl,
    rid,
    objects,
    selectedBid,
    isLoading,
    error,
    setImageFile,
    setSelectedBid,
    clear,
    submitDetection,
  } = useDetectionStore();

  const selectedObject = objects.find((item) => item.bid === selectedBid) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        badge="已連接後端 API"
        title="影像辨識"
        description="上傳單張圖片後，呼叫 Python 後端執行 OpenCV DataMatrix 偵測、標記與解碼。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => submitDetection()} disabled={!imageFile || isLoading}>
              <Play size={16} />
              {isLoading ? "辨識中..." : "開始辨識"}
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

          <SectionCard title="辨識摘要" description="本次辨識摘要與目前選取物件資訊。">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
                <span className="text-muted-foreground">批次編號 (RID)</span>
                <span className="font-medium">{rid ?? "尚未執行"}</span>
              </div>
              <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
                <span className="text-muted-foreground">物件數量</span>
                <span className="font-medium">{objects.length}</span>
              </div>
              <div className="rounded-xl border p-4 shadow-sm bg-background/50">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">目前選取物件</p>
                {selectedObject ? (
                  <div className="space-y-2">
                    <p className="font-mono text-sm font-semibold break-all">{selectedObject.bid}</p>
                    <p className="text-sm text-muted-foreground break-all">條碼： {selectedObject.barcodeValue ?? "未偵測到條碼"}</p>
                    <p className="text-sm text-muted-foreground break-words">OCR： {selectedObject.ocrText ?? "無"}</p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">尚未選取物件</p>
                )}
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <DetectionCanvas
              imageUrl={imageUrl}
              objects={objects}
              selectedBid={selectedBid}
              onSelect={setSelectedBid}
            />
          </motion.div>

          <SectionCard
            title="辨識結果列表"
            description="辨識結果列表與框選互動同步。"
            action={
              <Button variant="outline" disabled={!objects.length}>
                <DownloadSimple size={16} />
                下載結果
              </Button>
            }
          >
            {objects.length ? (
              <ObjectResultTable items={objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
            ) : (
              <EmptyState title="尚無辨識結果" description="先上傳圖片並按下開始辨識，即可查看後端回傳的辨識結果。" />
            )}
          </SectionCard>
        </div>
      </section>
    </div>
  );
}
