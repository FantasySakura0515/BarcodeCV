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

  const handleFileSelect = (file: File | null) => {
    clear();
    if (file) {
      setImageFile(file);
    }
  };

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

      <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <div className="flex flex-col space-y-6">
          <UploadDropzone onFileSelect={handleFileSelect} fileName={imageFile?.name} />

          <SectionCard title="掃描摘要" description="目前分析狀態與所選目標。" className="shrink-0 border-[#00f0ff]/20 bg-[#0b0c10]/60 backdrop-blur-md">
            <div className="space-y-3 text-sm font-mono">
              <div className="flex items-center justify-between rounded border border-[#334155] bg-[#1a202c]/50 px-3 py-2">
                <span className="text-[#94a3b8]">批次處理號</span>
                <span className="font-semibold text-[#00f0ff]">{rid ?? "等待中..."}</span>
              </div>
              <div className="flex items-center justify-between rounded border border-[#334155] bg-[#1a202c]/50 px-3 py-2">
                <span className="text-[#94a3b8]">已偵測物件</span>
                <span className="font-semibold text-[#00ff66]">{objects.length} 個</span>
              </div>
              <div className="rounded border border-[#334155] bg-[#1a202c]/80 p-4 shadow-[inset_0_0_10px_#000000]">
                <p className="mb-2 text-[10px] font-bold tracking-[0.2em] text-[#00f0ff] flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#00f0ff] animate-pulse" />
                  目標已鎖定
                </p>
                {selectedObject ? (
                  <div className="space-y-2">
                    <p className="break-all text-xs font-semibold text-white">{selectedObject.bid}</p>
                    <p className="break-all text-sm">
                      <span className="text-[#94a3b8]">解碼結果: </span>
                      <span className={selectedObject.barcodeValue ? "text-[#00ff66]" : "text-[#ef4444]"}>
                        {selectedObject.barcodeValue ?? "無法解析"}
                      </span>
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-[#94a3b8] italic">尚未選取任何物件。</p>
                )}
              </div>
              {error && (
                <div className="rounded border border-[#ef4444]/50 bg-[#ef4444]/10 p-3">
                  <p className="text-xs text-[#ef4444] mb-2">{error}</p>
                  <Button size="sm" variant="destructive" onClick={() => submitDetection()} disabled={!imageFile || isLoading}>
                    重新執行分析
                  </Button>
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        <div className="flex flex-col min-h-[500px]">
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="h-full relative group">
            <div className="absolute inset-0 rounded-[0.5rem] border border-[#00f0ff]/30 bg-[#0b0c10] shadow-[0_0_20px_rgba(0,240,255,0.05)] overflow-hidden flex flex-col">
              <div className="h-10 border-b border-[#00f0ff]/20 bg-[#00f0ff]/5 flex items-center px-4 justify-between shrink-0">
                <div className="flex gap-2 items-center">
                  <span className="block w-2 h-2 bg-[#ef4444] rounded-full"></span>
                  <span className="block w-2 h-2 bg-[#f59e0b] rounded-full"></span>
                  <span className="block w-2 h-2 bg-[#00ff66] rounded-full"></span>
                  <span className="ml-2 text-[11px] font-mono font-bold text-[#00f0ff] tracking-widest">影像視覺化分析平台</span>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    className="h-6 text-[10px] px-2 rounded font-mono"
                    variant={showBoundingBoxes ? "default" : "outline"}
                    onClick={() => setShowBoundingBoxes((current) => !current)}
                  >
                    {showBoundingBoxes ? "隱藏外框" : "顯示外框"}
                  </Button>
                  <Button
                    size="sm"
                    className="h-6 text-[10px] px-2 rounded font-mono"
                    variant={showDecodeInfo ? "default" : "outline"}
                    onClick={() => setShowDecodeInfo((current) => !current)}
                    disabled={!showBoundingBoxes}
                  >
                    {showDecodeInfo ? "隱藏編號" : "顯示編號"}
                  </Button>
                </div>
              </div>
              <div className="flex-1 relative bg-[url('/grid-pattern.svg')] bg-center bg-repeat bg-[size:20px_20px] overflow-hidden">
                <DetectionCanvas
                  imageUrl={imageUrl}
                  objects={objects}
                  selectedBid={selectedBid}
                  onSelect={setSelectedBid}
                  showBoundingBoxes={showBoundingBoxes}
                  showDecodeInfo={showDecodeInfo}
                />
                {/* Techy overlay corners */}
                <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-[#00f0ff] pointer-events-none md:m-4" />
                <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-[#00f0ff] pointer-events-none md:m-4" />
                <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-[#00f0ff] pointer-events-none md:m-4" />
                <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-[#00f0ff] pointer-events-none md:m-4" />
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      <div className="w-full">
        <SectionCard
          title="分析矩陣"
          description="系統擷取的物件與特徵資料清單。"
          className="w-full border-[#334155]/50 bg-[#161b22]/80"
          action={
            <Button variant="outline" size="sm" disabled={!objects.length} className="h-7 text-[10px] border-[#00f0ff]/30 text-[#00f0ff] hover:bg-[#00f0ff]/10 tracking-widest font-mono">
              <DownloadSimple size={14} className="mr-1" />
              匯出資料
            </Button>
          }
        >
          {objects.length ? (
            <ObjectResultTable items={objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
          ) : (
            <EmptyState title="等待影像載入" description="系統尚未取得目標資料，請上傳並執行掃描程序" />
          )}
        </SectionCard>
      </div>
    </div>
  );
}
