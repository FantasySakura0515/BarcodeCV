import { notFound } from "next/navigation";

import { EmptyState } from "@/components/common/empty-state";
import { ModelBadge } from "@/components/common/model-badge";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { DetectionCanvas } from "@/components/detection/detection-canvas";
import { ObjectResultTable } from "@/components/detection/object-result-table";
import { fetchBatch } from "@/lib/api/client";

export default async function BatchDetailPage({ params }: { params: Promise<{ rid: string }> }) {
  const { rid } = await params;
  const batch = await fetchBatch(rid).catch(() => null);

  if (!batch) {
    notFound();
  }

  const previewImageUrl = batch.objects[0]?.imagePath ?? null;

  return (
    <div className="space-y-6">
      <PageHeader badge="Batch detail" title={batch.rid} description="Review object-level results and bounding boxes for this run." />

      <section className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <SectionCard title="Image preview" description="Bounding boxes rendered from detection results.">
          <DetectionCanvas imageUrl={previewImageUrl} objects={batch.objects} selectedBid={batch.objects[0]?.bid ?? null} />
        </SectionCard>

        <SectionCard title="Run summary" description="Barcode/OCR output summary and model attribution.">
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>Run ID (RID)</span><span className="font-medium">{batch.rid}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>Objects</span><span className="font-medium">{batch.objectCount}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>Barcode success</span><span className="font-medium">{batch.barcodeSuccessCount}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>Model</span><ModelBadge model={batch.model} /></div>
          </div>
        </SectionCard>
      </section>

      <SectionCard title="Detected objects" description="All objects detected in this run.">
        {batch.objects.length ? (
          <ObjectResultTable items={batch.objects} selectedBid={batch.objects[0]?.bid ?? null} />
        ) : (
          <EmptyState title="No objects in this run" description="This run does not contain object-level results." />
        )}
      </SectionCard>
    </div>
  );
}
