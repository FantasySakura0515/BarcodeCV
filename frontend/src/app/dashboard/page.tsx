import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { ModelBadge } from "@/components/common/model-badge";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { StatCard } from "@/components/common/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchStatsSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let statsSummary;

  try {
    statsSummary = await fetchStatsSummary();
  } catch {
    return (
      <div className="space-y-6">
        <PageHeader
          badge="營運總覽"
          title="儀表板"
          description="檢視辨識活動、趨勢與模型使用情況的系統摘要。"
        />
        <EmptyState
          title="無法載入儀表板資料"
          description="API 請求失敗。請確認後端連線狀態後重新整理此頁再試。"
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        badge="營運總覽"
        title="儀表板"
        description="監控辨識吞吐量、成功率與目前啟用的模型設定。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/detection">執行影像辨識</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/live-detection">開啟即時辨識</Link>
            </Button>
          </div>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="累計辨識批次" value={String(statsSummary.totalRounds)} hint="所有已記錄批次" />
        <StatCard label="累計物件數" value={String(statsSummary.totalObjects)} hint="所有已偵測物件" />
        <StatCard label="條碼讀取率" value={`${statsSummary.barcodeSuccessRate}%`} hint="近期平均" />
        <StatCard label="OCR 成功率" value={`${statsSummary.ocrSuccessRate}%`} hint="整體 OCR 表現" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <SectionCard title="近期批次" description="最新辨識批次與摘要。">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>批次 ID（RID）</TableHead>
                <TableHead>物件數</TableHead>
                <TableHead>條碼成功數</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>建立時間</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {statsSummary.recentRounds.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-20 text-center text-sm text-muted-foreground">
                    尚無批次紀錄。
                  </TableCell>
                </TableRow>
              ) : null}
              {statsSummary.recentRounds.map((batch) => (
                <TableRow key={batch.rid}>
                  <TableCell className="font-medium">
                    <Link className="text-primary" href={`/batches/${batch.rid}`}>
                      {batch.rid}
                    </Link>
                  </TableCell>
                  <TableCell>{batch.objectCount}</TableCell>
                  <TableCell>
                    {batch.barcodeSuccessCount}/{batch.objectCount}
                  </TableCell>
                  <TableCell>
                    <ModelBadge model={batch.model} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{new Date(batch.createdAt).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="啟用模型" description="目前啟用的前處理與辨識設定。">
            <div className="space-y-3">
              <div className="rounded-xl border bg-background p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">OpenCV 輪廓偵測</p>
                    <p className="text-sm text-muted-foreground">主要 Data Matrix 偵測與解碼流程。</p>
                  </div>
                  <Badge variant="success">啟用中</Badge>
                </div>
              </div>
              <div className="rounded-xl border p-4">
                <p className="font-medium">Data Matrix 解碼器</p>
                <p className="mt-1 text-sm text-muted-foreground">採用 pylibdmtx，並以 zxing-cpp 作為備援解碼器。</p>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="每週趨勢" description="偵測物件數的簡化趨勢檢視。">
            <div className="space-y-3">
              {statsSummary.trends.map((trend) => (
                <div key={trend.label} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{trend.label}</span>
                    <span className="text-muted-foreground">{trend.objects} 個物件</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min((trend.objects / 150) * 100, 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      </section>
    </div>
  );
}
