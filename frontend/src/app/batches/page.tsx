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
        <PageHeader badge="Record review" title="Batch Records" description="Review historical detection runs and outcomes." />
        <EmptyState
          title="Unable to load batch records"
          description="The API request failed. Check backend availability and refresh to retry."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        badge="Record review"
        title="Batch Records"
        description="Track historical runs, barcode/OCR outcomes, and model attribution."
      />

      <SectionCard title="Batch list" description="Detection runs returned by backend API.">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Run ID (RID)</TableHead>
              <TableHead>Objects</TableHead>
              <TableHead>Barcode success</TableHead>
              <TableHead>OCR success</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {batches.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-20 text-center text-sm text-muted-foreground">
                  No batch records available.
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
