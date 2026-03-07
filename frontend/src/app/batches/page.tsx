import Link from "next/link";

import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { ModelBadge } from "@/components/common/model-badge";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchBatches } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function BatchesPage() {
  const batches = await fetchBatches();

  return (
    <div className="space-y-6">
      <PageHeader
        badge="歷史紀錄"
        title="批次檢測紀錄"
        description="查詢歷史批次、成功率與模型資訊，供追蹤與統計使用。"
      />

      <SectionCard title="搜尋與列表" description="目前顯示後端資料，搜尋列保留作為下一階段篩選介面。">
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <Input placeholder="搜尋 RID / 條碼 / 日期" />
          <Input placeholder="模型類型，例如 opencv" />
          <Input placeholder="狀態，例如 success" />
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>批次編號 (RID)</TableHead>
              <TableHead>物件總數</TableHead>
              <TableHead>條碼成功數</TableHead>
              <TableHead>OCR 成功數</TableHead>
              <TableHead>模型類型</TableHead>
              <TableHead>建立時間</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {batches.map((batch) => (
              <TableRow key={batch.rid}>
                <TableCell className="font-medium">
                  <Link href={`/batches/${batch.rid}`} className="text-primary">
                    {batch.rid}
                  </Link>
                </TableCell>
                <TableCell>{batch.objectCount}</TableCell>
                <TableCell>{batch.barcodeSuccessCount}</TableCell>
                <TableCell>{batch.ocrSuccessCount}</TableCell>
                <TableCell><ModelBadge model={batch.model} /></TableCell>
                <TableCell className="text-muted-foreground">{new Date(batch.createdAt).toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SectionCard>
    </div>
  );
}
