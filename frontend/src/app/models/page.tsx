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
        <PageHeader badge="model list" title="Models" description="View active models and available versions used by the recognition service." />
        <EmptyState
          title="Failed to load model data"
          description="API request failed. Check backend connection and refresh to try again."
        />
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader badge="model list" title="Models" description="View active models and available versions used by the recognition service." />
        <EmptyState title="No model records" description="The backend API does not currently provide model metadata." />
      </div>
    );
  }

  const activeModel = models.find((item) => item.isActive && item.modelType === "opencv") ?? models[0];

  return (
    <div className="space-y-6">
      <PageHeader
        badge="model list"
        title="Models"
        description="View active model configuration and available versions for operational tracking."
      />

      <section className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <SectionCard title="Active Model" description="The production model currently used by the recognition pipeline.">
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

        <SectionCard title="Model List" description="Model metadata provided by the backend API.">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>類型</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>框架</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead>更新時間</TableHead>
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
                    <Badge variant={model.isActive ? "success" : "outline"}>{model.isActive ? "啟用中" : "未啟用"}</Badge>
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
