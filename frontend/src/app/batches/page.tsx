import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { ModelBadge } from "@/components/common/model-badge";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchBatches } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function BatchesPage() {
  let batches;

  try {
    batches = await fetchBatches();
  } catch {
    return (
      <div className="space-y-6">
        <PageHeader badge="紀錄檢視" title="批次紀錄" description="檢視歷史辨識批次與結果。" />
        <EmptyState
          title="無法載入批次紀錄"
          description="API 請求失敗。請檢查後端可用性並重新整理後再試。"
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        badge="紀錄檢視"
        title="批次紀錄"
        description="追蹤歷史批次、條碼與 OCR 結果，以及模型來源。"
      />

      <SectionCard title="批次清單" description="後端 API 回傳的辨識批次。">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>批次 ID（RID）</TableHead>
              <TableHead>物件數</TableHead>
              <TableHead>條碼成功數</TableHead>
              <TableHead>OCR 成功數</TableHead>
              <TableHead>模型</TableHead>
              <TableHead>建立時間</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {batches.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-20 text-center text-sm text-muted-foreground">
                  目前沒有批次紀錄。
                </TableCell>
              </TableRow>
            ) : null}
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
                <TableCell>
                  <ModelBadge model={batch.model} />
                </TableCell>
                <TableCell className="text-muted-foreground">{new Date(batch.createdAt).toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SectionCard>
    </div>
  );
}
