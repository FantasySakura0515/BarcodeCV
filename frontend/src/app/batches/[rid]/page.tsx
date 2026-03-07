import { notFound } from "next/navigation";

import { ModelBadge } from "@/components/common/model-badge";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { DetectionCanvas } from "@/components/detection/detection-canvas";
import { ObjectResultTable } from "@/components/detection/object-result-table";
import { fetchBatch } from "@/lib/api/client";
import { resolveApiAssetUrl } from "@/lib/api/config";

export default async function BatchDetailPage({ params }: { params: Promise<{ rid: string }> }) {
  const { rid } = await params;
  const batch = await fetchBatch(rid).catch(() => null);

  if (!batch) {
    notFound();
  }

  const previewImageUrl = resolveApiAssetUrl(batch.objects[0]?.imagePath);

  return (
    <div className="space-y-6">
      <PageHeader
        badge="批次詳細資料"
        title={batch.rid}
        description="查看批次下所有物件結果與框選資訊。"
      />

      <section className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <SectionCard title="批次影像預覽" description="目前以前端示意畫布呈現框選位置。">
          <DetectionCanvas imageUrl={previewImageUrl} objects={batch.objects} selectedBid={batch.objects[0]?.bid ?? null} />
        </SectionCard>

        <SectionCard title="批次摘要資訊" description="包含成功率與模型使用狀況。">
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>批次編號 (RID)</span><span className="font-medium">{batch.rid}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>偵測物件總數</span><span className="font-medium">{batch.objectCount}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>成功解析條碼數</span><span className="font-medium">{batch.barcodeSuccessCount}</span></div>
            <div className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2"><span>使用模型</span><ModelBadge model={batch.model} /></div>
          </div>
        </SectionCard>
      </section>

      <SectionCard title="辨識物件列表" description="本批次所有辨識物件明細。">
        <ObjectResultTable items={batch.objects} selectedBid={batch.objects[0]?.bid ?? null} />
      </SectionCard>
    </div>
  );
}
