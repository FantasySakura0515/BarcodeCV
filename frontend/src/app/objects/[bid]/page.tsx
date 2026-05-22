import { notFound } from "next/navigation";

import { ModelBadge } from "@/components/common/model-badge";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { Textarea } from "@/components/ui/textarea";
import { fetchObject } from "@/lib/api/client";

export default async function ObjectDetailPage({ params }: { params: Promise<{ bid: string }> }) {
  const { bid } = await params;
  const item = await fetchObject(bid).catch(() => null);

  if (!item) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <PageHeader badge="Object Detail" title={item.bid} description="View the barcode, OCR, and metadata for a single detected object." />

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionCard title="recognition output" description="location and recognition results for this object.">
          <div className="grid gap-3 md:grid-cols-2">
            <Info label="Batch ID (RID)" value={item.rid} />
            <Info label="Object ID (BID)" value={item.bid} />
            <Info label="barcode value" value={item.barcodeValue ?? "not detected"} />
            <Info label="barcode type" value={item.barcodeType ?? "unknown"} />
            <Info label="confidence score" value={`${Math.round(item.confidenceScore * 100)}%`} />
            <Info label="created at" value={new Date(item.createdAt).toLocaleString()} />
          </div>
          <div className="mt-4 rounded-xl border bg-background p-4">
            <p className="mb-2 text-sm font-medium">OCR text</p>
            <p className="text-sm leading-6 text-muted-foreground">{item.ocrText ?? "no OCR text."}</p>
          </div>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="model metadata" description="model info bound to this result.">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span>name</span><span className="font-medium">{item.model.modelName}</span></div>
              <div className="flex items-center justify-between"><span>version</span><span className="font-medium">{item.model.modelVersion}</span></div>
              <div className="flex items-center justify-between"><span>framework</span><span className="font-medium">{item.model.framework}</span></div>
              <div className="flex items-center justify-between"><span>status</span><ModelBadge model={item.model} /></div>
            </div>
          </SectionCard>

          <SectionCard title="remarks" description="read-only placeholder for object remarks.">
            <Textarea defaultValue={item.remark ?? ""} placeholder="no remarks" className="min-h-25 resize-y" />
          </SectionCard>
        </div>
      </section>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-muted/30 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 break-all text-sm font-medium">{value}</p>
    </div>
  );
}
