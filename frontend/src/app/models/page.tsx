import { PageHeader } from "@/components/common/page-header";
import { SectionCard } from "@/components/common/section-card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchModels } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const models = await fetchModels();
  const activeModel = models.find((item) => item.isActive && item.modelType === "opencv") ?? models[0];

  return (
    <div className="space-y-6">
      <PageHeader
        badge="版本管理"
        title="模型管理中心"
        description="檢視目前啟用與候選模型，後續可接入正式模型管理流程。"
      />

      <section className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <SectionCard title="上線中的辨識模型" description="目前正式使用中的偵測模型。">
          <div className="rounded-2xl border bg-primary/5 p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-lg font-semibold">{activeModel.modelName}</p>
                <p className="mt-1 text-sm text-muted-foreground">{activeModel.framework} · {activeModel.modelVersion}</p>
              </div>
              <Badge variant="success">使用中</Badge>
            </div>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">{activeModel.remark}</p>
          </div>
        </SectionCard>

        <SectionCard title="模型列表" description="模型資訊表，目前由 Python 後端即時提供。">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>模型名稱</TableHead>
                <TableHead>類型</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>使用框架</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead>更新日期</TableHead>
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
                    <Badge variant={model.isActive ? "success" : "outline"}>{model.isActive ? "使用中" : "停用"}</Badge>
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
