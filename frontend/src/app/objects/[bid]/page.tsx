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
      <PageHeader
        badge="物件詳細資料"
        title={item.bid}
        description="檢視單一物件的條碼、OCR 文字與對應模型資訊。"
      />

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionCard title="辨識與定位內容" description="物件在圖片中的定位座標與辨識結果。">
          <div className="grid gap-3 md:grid-cols-2">
            <Info label="批次編號 (RID)" value={item.rid} />
            <Info label="物件編號 (BID)" value={item.bid} />
            <Info label="讀取條碼" value={item.barcodeValue ?? "無法讀取"} />
            <Info label="條碼類型" value={item.barcodeType ?? "未知"} />
            <Info label="辨識信心度" value={`${Math.round(item.confidenceScore * 100)}%`} />
            <Info label="建立時間" value={new Date(item.createdAt).toLocaleString()} />
          </div>
          <div className="mt-4 rounded-xl border p-4 bg-background/50">
            <p className="mb-2 text-sm font-medium">OCR 辨識文字</p>
            <p className="text-sm leading-6 text-muted-foreground">{item.ocrText ?? "無辨識內容"}</p>
          </div>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="模型資訊" description="此筆資料所綁定之模型版本。">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span>模型名稱</span><span className="font-medium">{item.model.modelName}</span></div>
              <div className="flex items-center justify-between"><span>版本</span><span className="font-medium">{item.model.modelVersion}</span></div>
              <div className="flex items-center justify-between"><span>框架</span><span className="font-medium">{item.model.framework}</span></div>
              <div className="flex items-center justify-between"><span>狀態</span><ModelBadge model={item.model} /></div>
            </div>
          </SectionCard>

          <SectionCard title="物件備註" description="目前先以靜態欄位呈現，後續可接 PATCH API。">
            <Textarea defaultValue={item.remark ?? ""} placeholder="輸入備註內容..." className="min-h-25 resize-y" />
          </SectionCard>
        </div>
      </section>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-muted/30 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-medium break-all">{value}</p>
    </div>
  );
}
