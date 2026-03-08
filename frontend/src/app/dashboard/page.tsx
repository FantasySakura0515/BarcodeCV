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
          badge="Operations overview"
          title="Dashboard"
          description="System summary of detection activity, trends, and model usage."
        />
        <EmptyState
          title="Unable to load dashboard data"
          description="The API request failed. Verify backend connectivity and refresh this page to retry."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        badge="Operations overview"
        title="Dashboard"
        description="Monitor detection throughput, success rates, and active model configuration."
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/detection">Run image detection</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/live-detection">Open live detection</Link>
            </Button>
          </div>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total detection runs" value={String(statsSummary.totalRounds)} hint="All recorded runs" />
        <StatCard label="Total objects" value={String(statsSummary.totalObjects)} hint="All detected objects" />
        <StatCard label="Barcode read rate" value={`${statsSummary.barcodeSuccessRate}%`} hint="Recent average" />
        <StatCard label="OCR success rate" value={`${statsSummary.ocrSuccessRate}%`} hint="Overall OCR performance" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <SectionCard title="Recent runs" description="Latest detection runs and summaries.">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run ID (RID)</TableHead>
                <TableHead>Objects</TableHead>
                <TableHead>Barcode success</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {statsSummary.recentRounds.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-20 text-center text-sm text-muted-foreground">
                    No runs recorded yet.
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
          <SectionCard title="Active model" description="Currently active preprocessing and recognition configuration.">
            <div className="space-y-3">
              <div className="rounded-xl border bg-background p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">OpenCV contour detection</p>
                    <p className="text-sm text-muted-foreground">Primary DataMatrix detection and decoding pipeline.</p>
                  </div>
                  <Badge variant="success">Active</Badge>
                </div>
              </div>
              <div className="rounded-xl border p-4">
                <p className="font-medium">DataMatrix decoder</p>
                <p className="mt-1 text-sm text-muted-foreground">Uses pylibdmtx and zxing-cpp as fallback decoders.</p>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Weekly trend" description="Simplified trend view of detected objects.">
            <div className="space-y-3">
              {statsSummary.trends.map((trend) => (
                <div key={trend.label} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{trend.label}</span>
                    <span className="text-muted-foreground">{trend.objects} objects</span>
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
