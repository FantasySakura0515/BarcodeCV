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
        <PageHeader badge="模型清單" title="模型" description="檢視辨識服務使用中的啟用模型與可用版本。" />
        <EmptyState
          title="無法載入模型資料"
          description="API 請求失敗。請確認後端連線後重新整理再試。"
        />
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader badge="模型清單" title="模型" description="檢視辨識服務使用中的啟用模型與可用版本。" />
        <EmptyState title="沒有模型紀錄" description="目前後端 API 尚未提供模型中繼資料。" />
      </div>
    );
  }

  const activeModel = models.find((item) => item.isActive && item.modelType === "opencv") ?? models[0];

  return (
    <div className="space-y-6">
      <PageHeader
        badge="模型清單"
        title="模型"
        description="檢視目前啟用模型設定與可用版本，供營運追蹤。"
      />

      <section className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <SectionCard title="啟用模型" description="辨識流程目前使用的正式環境模型。">
          <div className="rounded-xl border bg-background p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-lg font-semibold">{activeModel.modelName}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {activeModel.framework} · {activeModel.modelVersion}
                </p>
              </div>
              <Badge variant="success">啟用中</Badge>
            </div>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">{activeModel.remark}</p>
          </div>
        </SectionCard>

        <SectionCard title="模型清單" description="後端 API 提供的模型中繼資料。">
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
