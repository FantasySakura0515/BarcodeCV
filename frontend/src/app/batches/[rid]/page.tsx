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
      <PageHeader badge="批次詳情" title={batch.rid} description="檢視本次批次的物件層級結果與邊界框。" />

      <section className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <SectionCard title="影像預覽" description="由辨識結果繪製邊界框。">
          <DetectionCanvas imageUrl={previewImageUrl} objects={batch.objects} selectedBid={batch.objects[0]?.bid ?? null} />
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
          <ObjectResultTable items={batch.objects} selectedBid={batch.objects[0]?.bid ?? null} />
        ) : (
          <EmptyState title="此批次沒有物件" description="此批次不包含物件層級結果。" />
        )}
      </SectionCard>
    </div>
  );
}
