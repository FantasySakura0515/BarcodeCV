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
      <PageHeader badge="物件詳情" title={item.bid} description="檢視單一偵測物件的條碼、OCR 與中繼資料。" />

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionCard title="辨識輸出" description="此物件的位置與辨識結果。">
          <div className="grid gap-3 md:grid-cols-2">
            <Info label="批次 ID（RID）" value={item.rid} />
            <Info label="物件 ID（BID）" value={item.bid} />
            <Info label="條碼值" value={item.barcodeValue ?? "未偵測到"} />
            <Info label="條碼類型" value={item.barcodeType ?? "未知"} />
            <Info label="信心分數" value={`${Math.round(item.confidenceScore * 100)}%`} />
            <Info label="建立時間" value={new Date(item.createdAt).toLocaleString()} />
          </div>
          <div className="mt-4 rounded-xl border bg-background p-4">
            <p className="mb-2 text-sm font-medium">OCR 文字</p>
            <p className="text-sm leading-6 text-muted-foreground">{item.ocrText ?? "沒有 OCR 文字。"}</p>
          </div>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="模型中繼資料" description="此結果綁定的模型資訊。">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span>名稱</span><span className="font-medium">{item.model.modelName}</span></div>
              <div className="flex items-center justify-between"><span>版本</span><span className="font-medium">{item.model.modelVersion}</span></div>
              <div className="flex items-center justify-between"><span>框架</span><span className="font-medium">{item.model.framework}</span></div>
              <div className="flex items-center justify-between"><span>狀態</span><ModelBadge model={item.model} /></div>
            </div>
          </SectionCard>

          <SectionCard title="備註" description="物件備註欄位的唯讀佔位區。">
            <Textarea defaultValue={item.remark ?? ""} placeholder="無備註" className="min-h-25 resize-y" />
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
