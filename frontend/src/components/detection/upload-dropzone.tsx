"use client";

import { ImageSquare, UploadSimple } from "@phosphor-icons/react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function UploadDropzone({
  onFileSelect,
  fileName,
}: {
  onFileSelect: (file: File | null) => void;
  fileName?: string;
}) {
  return (
    <Card className="border-dashed border-primary/30 bg-primary/5">
      <CardContent className="flex flex-col items-center justify-center gap-4 py-10 text-center">
        <div className="rounded-full bg-background p-3 text-primary shadow-sm">
          <UploadSimple size={24} weight="duotone" />
        </div>
        <div>
          <p className="text-base font-medium">拖曳圖片到此處或直接選擇檔案</p>
          <p className="mt-1 text-sm text-muted-foreground">支援單張圖片，送到後端執行 DataMatrix 偵測與解碼。</p>
        </div>
        <label>
          <input
            className="hidden"
            type="file"
            accept="image/*"
            onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
          />
          <Button asChild>
            <span>選擇圖片</span>
          </Button>
        </label>
        {fileName ? (
          <div className="flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground">
            <ImageSquare size={14} />
            {fileName}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
