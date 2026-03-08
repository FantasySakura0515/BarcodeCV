import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchModels } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  let models;

  try {
    models = await fetchModels();
  } catch {
    return (
      <div className="space-y-6">
        <PageHeader badge="Model inventory" title="Models" description="View active and available model versions used by detection services." />
        <EmptyState
          title="Unable to load model data"
          description="The API request failed. Verify backend connectivity and refresh to retry."
        />
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader badge="Model inventory" title="Models" description="View active and available model versions used by detection services." />
        <EmptyState title="No model records" description="No model metadata is currently available from backend API." />
      </div>
    );
  }

  const activeModel = models.find((item) => item.isActive && item.modelType === "opencv") ?? models[0];

  return (
    <div className="space-y-6">
      <PageHeader
        badge="Model inventory"
        title="Models"
        description="Review active model configuration and available versions for operations tracking."
      />

      <section className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <SectionCard title="Active model" description="Current production model used by the detection pipeline.">
          <div className="rounded-xl border bg-background p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-lg font-semibold">{activeModel.modelName}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {activeModel.framework} · {activeModel.modelVersion}
                </p>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">{activeModel.remark}</p>
          </div>
        </SectionCard>

        <SectionCard title="Model list" description="Model metadata provided by backend API.">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Framework</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models.map((model) => (
                <TableRow key={model.id}>
                  <TableCell className="font-medium">{model.modelName}</TableCell>
                  <TableCell>{model.modelType}</TableCell>
                  <TableCell>{model.modelVersion}</TableCell>
                  <TableCell>{model.framework}</TableCell>
                  <TableCell>
                    <Badge variant={model.isActive ? "success" : "outline"}>{model.isActive ? "Active" : "Inactive"}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{new Date(model.updatedAt).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SectionCard>
      </section>
    </div>
  );
}
