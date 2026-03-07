import Link from "next/link";

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
  const statsSummary = await fetchStatsSummary();

  return (
    <div className="space-y-6">
      <PageHeader
        badge="MVP 控制台"
        title="辨識系統儀表板"
        description="總覽批次、模型與辨識成功率，作為操作人員的第一層視圖。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/detection">影像辨識</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/live-detection">即時辨識</Link>
            </Button>
          </div>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="總檢測批次" value={String(statsSummary.totalRounds)} hint="累積檢測批次" />
        <StatCard label="總偵測物件" value={String(statsSummary.totalObjects)} hint="累積辨識物件" />
        <StatCard label="條碼讀取率" value={`${statsSummary.barcodeSuccessRate}%`} hint="近期平均成功率" />
        <StatCard label="文字辨識率" value={`${statsSummary.ocrSuccessRate}%`} hint="整體 OCR 辨識表現" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <SectionCard title="近期檢測批次" description="最近批次與摘要結果。">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>批次編號 (RID)</TableHead>
                <TableHead>物件數量</TableHead>
                <TableHead>讀取條碼</TableHead>
                <TableHead>使用模型</TableHead>
                <TableHead>建立時間</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {statsSummary.recentRounds.map((batch) => (
                <TableRow key={batch.rid}>
                  <TableCell className="font-medium">
                    <Link className="text-primary" href={`/batches/${batch.rid}`}>
                      {batch.rid}
                    </Link>
                  </TableCell>
                  <TableCell>{batch.objectCount}</TableCell>
                  <TableCell>{batch.barcodeSuccessCount}/{batch.objectCount}</TableCell>
                  <TableCell><ModelBadge model={batch.model} /></TableCell>
                  <TableCell className="text-muted-foreground">{new Date(batch.createdAt).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="啟用中模型" description="目前啟用中的前處理與辨識模型。">
            <div className="space-y-3">
              <div className="rounded-2xl border bg-primary/5 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">OpenCV 輪廓偵測</p>
                    <p className="text-sm text-muted-foreground">DataMatrix 偵測與解碼主流程</p>
                  </div>
                  <Badge variant="success">使用中</Badge>
                </div>
              </div>
              <div className="rounded-2xl border p-4">
                <p className="font-medium">DataMatrix 解碼器</p>
                <p className="mt-1 text-sm text-muted-foreground">使用 pylibdmtx 與 zxing-cpp 作為多重解碼備援。</p>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="本週辨識趨勢" description="示意圖先以簡化柱狀視覺呈現。">
            <div className="space-y-3">
              {statsSummary.trends.map((trend) => (
                <div key={trend.label} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{trend.label}</span>
                    <span className="text-muted-foreground">{trend.objects} 個物件</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div
                      className="h-2 rounded-full bg-primary"
                      style={{ width: `${Math.min((trend.objects / 150) * 100, 100)}%` }}
                    />
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
