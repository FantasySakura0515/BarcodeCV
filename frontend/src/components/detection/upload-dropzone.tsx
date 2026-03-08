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
    <Card className="border-dashed bg-card">
      <CardContent className="flex flex-col items-center justify-center gap-4 py-10 text-center">
        <div className="rounded-full bg-muted p-3 text-muted-foreground">
          <UploadSimple size={22} />
        </div>
        <div>
          <p className="text-base font-medium">上傳影像檔案</p>
          <p className="mt-1 text-sm text-muted-foreground">僅支援單張影像，檔案將送往後端辨識服務。</p>
        </div>
        <label>
          <input
            className="hidden"
            type="file"
            accept="image/*"
            onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
          />
          <Button asChild>
            <span>選擇檔案</span>
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
