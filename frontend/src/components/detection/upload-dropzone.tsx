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
    <Card className="relative overflow-hidden border border-[#334155]/50 bg-[#0b0c10]/40 backdrop-blur-sm group transition-colors hover:border-[#00f0ff]/40 shrink-0">
      <div className="absolute top-0 right-0 w-16 h-16 bg-[url('/scan-grid.svg')] bg-[#00f0ff]/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none rounded-bl-full" />
      <CardContent className="flex flex-col items-center justify-center gap-3 py-6 text-center">
        <div className="rounded bg-[#1a202c] p-3 text-[#00f0ff] shadow-[0_0_10px_#00f0ff20] border border-[#00f0ff]/20">
          <UploadSimple size={20} weight="duotone" className="group-hover:animate-bounce" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-mono tracking-wider text-[#e2e8f0]">影像輸入模組</p>
          <p className="text-xs font-mono text-[#94a3b8] tracking-widest">等待單張影像上傳以進行分析</p>
        </div>
        <label className="mt-2 w-full max-w-[200px]">
          <input
            className="hidden"
            type="file"
            accept="image/*"
            onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
          />
          <Button asChild className="w-full bg-[#1e293b] hover:bg-[#00f0ff]/20 text-[#00f0ff] border border-[#00f0ff]/30 font-mono tracking-widest transition-all cursor-pointer">
            <span>{fileName ? "更換影像" : "選擇影像"}</span>
          </Button>
        </label>
        {fileName && (
          <div className="flex w-full max-w-[200px] justify-center items-center gap-2 rounded border border-[#00ff66]/30 bg-[#0b0c10] px-3 py-1.5 text-xs text-[#00ff66] font-mono truncate shadow-[0_0_8px_#00ff6620] mt-1">
            <ImageSquare size={14} className="shrink-0" />
            <span className="truncate">{fileName}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
