import { Badge } from "@/components/ui/badge";
import type { ModelInfo } from "@/types";

export function ModelBadge({ model }: { model: ModelInfo }) {
  const variant = model.modelType === "opencv" ? "default" : model.modelType === "yolo" ? "warning" : "success";
  return <Badge variant={variant}>{model.modelType.toUpperCase()} · {model.modelVersion}</Badge>;
}
