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
  const { imageFile, imageUrl, rid, objects, selectedBid, isLoading, error, setImageFile, setSelectedBid, clear, submitDetection } =
    useDetectionStore();

  const selectedObject = objects.find((item) => item.bid === selectedBid) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        badge="Image workflow"
        title="Image Detection"
        description="Upload one image, run backend detection, and review object-level barcode/OCR results."
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => submitDetection()} disabled={!imageFile || isLoading}>
              <Play size={16} />
              {isLoading ? "Running..." : "Run detection"}
            </Button>
            <Button variant="outline" onClick={clear}>
              <Trash size={16} />
              Clear
            </Button>
          </div>
        }
      />

      <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <div className="space-y-6">
          <UploadDropzone onFileSelect={setImageFile} fileName={imageFile?.name} />

          <SectionCard title="Run summary" description="Current run status and selected object information.">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
                <span className="text-muted-foreground">Run ID (RID)</span>
                <span className="font-medium">{rid ?? "Not started"}</span>
              </div>
              <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
                <span className="text-muted-foreground">Detected objects</span>
                <span className="font-medium">{objects.length}</span>
              </div>
              <div className="rounded-xl border bg-background p-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Selected object</p>
                {selectedObject ? (
                  <div className="space-y-2">
                    <p className="break-all font-mono text-sm font-semibold">{selectedObject.bid}</p>
                    <p className="break-all text-sm text-muted-foreground">Barcode: {selectedObject.barcodeValue ?? "Not detected"}</p>
                    <p className="break-words text-sm text-muted-foreground">OCR: {selectedObject.ocrText ?? "None"}</p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No object selected.</p>
                )}
              </div>
              {error ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3">
                  <p className="text-sm text-destructive">{error}</p>
                  <Button size="sm" variant="outline" className="mt-2" onClick={() => submitDetection()} disabled={!imageFile || isLoading}>
                    Retry
                  </Button>
                </div>
              ) : null}
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <DetectionCanvas imageUrl={imageUrl} objects={objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
          </motion.div>

          <SectionCard
            title="Detection results"
            description="Object list and box selection are synchronized."
            action={
              <Button variant="outline" disabled={!objects.length}>
                <DownloadSimple size={16} />
                Export
              </Button>
            }
          >
            {objects.length ? (
              <ObjectResultTable items={objects} selectedBid={selectedBid} onSelect={setSelectedBid} />
            ) : (
              <EmptyState title="No detection results" description="Upload an image and run detection to view object-level results." />
            )}
          </SectionCard>
        </div>
      </section>
    </div>
  );
}
