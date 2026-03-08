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
      <PageHeader badge="Object detail" title={item.bid} description="Inspect barcode/OCR outputs and metadata for one detected object." />

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionCard title="Detection output" description="Location and recognition values for this object.">
          <div className="grid gap-3 md:grid-cols-2">
            <Info label="Run ID (RID)" value={item.rid} />
            <Info label="Object ID (BID)" value={item.bid} />
            <Info label="Barcode value" value={item.barcodeValue ?? "Not detected"} />
            <Info label="Barcode type" value={item.barcodeType ?? "Unknown"} />
            <Info label="Confidence" value={`${Math.round(item.confidenceScore * 100)}%`} />
            <Info label="Created" value={new Date(item.createdAt).toLocaleString()} />
          </div>
          <div className="mt-4 rounded-xl border bg-background p-4">
            <p className="mb-2 text-sm font-medium">OCR text</p>
            <p className="text-sm leading-6 text-muted-foreground">{item.ocrText ?? "No OCR text."}</p>
          </div>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="Model metadata" description="Model information attached to this result.">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span>Name</span><span className="font-medium">{item.model.modelName}</span></div>
              <div className="flex items-center justify-between"><span>Version</span><span className="font-medium">{item.model.modelVersion}</span></div>
              <div className="flex items-center justify-between"><span>Framework</span><span className="font-medium">{item.model.framework}</span></div>
              <div className="flex items-center justify-between"><span>Status</span><ModelBadge model={item.model} /></div>
            </div>
          </SectionCard>

          <SectionCard title="Remarks" description="Read-only placeholder for object remark field.">
            <Textarea defaultValue={item.remark ?? ""} placeholder="No remark" className="min-h-25 resize-y" />
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
