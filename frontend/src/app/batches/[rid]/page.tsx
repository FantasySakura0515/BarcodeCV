import { notFound } from "next/navigation";

import { PageHeader } from "@/components/common/page-header";
import { BatchDetailView } from "@/components/detection/batch-detail-view";
import { fetchBatch } from "@/lib/api/client";

export default async function BatchDetailPage({ params }: { params: Promise<{ rid: string }> }) {
  const { rid } = await params;
  const batch = await fetchBatch(rid).catch(() => null);

  if (!batch) {
    notFound();
  }
  return (
    <div className="space-y-6">
      <PageHeader badge="批次詳情" title={batch.rid} description="檢視本次批次的物件層級結果與邊界框。" />

      <BatchDetailView batch={batch} />
    </div>
  );
}
