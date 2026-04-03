"use client";

import Link from "next/link";

import { ModelBadge } from "@/components/common/model-badge";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { DetectionObject } from "@/types";

export function ObjectResultTable({
  items,
  selectedBid,
  onSelect,
}: {
  items: DetectionObject[];
  selectedBid: string | null;
  onSelect?: (bid: string) => void;
}) {
  return (
    <div className="w-full">
      <Table>
        <TableHeader className="bg-[#1a202c]/80 border-b border-[#334155]">
          <TableRow className="hover:bg-transparent">
            <TableHead className="font-mono text-xs text-[#00f0ff] tracking-wider">物件編號 (BID)</TableHead>
            <TableHead className="font-mono text-xs text-[#00f0ff] tracking-wider">條碼內容</TableHead>
            <TableHead className="font-mono text-xs text-[#00f0ff] tracking-wider hidden 2xl:table-cell">OCR 結果</TableHead>
            <TableHead className="font-mono text-xs text-[#00f0ff] tracking-wider">信心分數</TableHead>
            <TableHead className="font-mono text-xs text-[#00f0ff] tracking-wider hidden lg:table-cell">辨識模型</TableHead>
            <TableHead className="font-mono text-xs text-[#00f0ff] tracking-wider text-right">詳細資料</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.length === 0 ? (
            <TableRow className="hover:bg-transparent border-b-[#334155]/30">
              <TableCell colSpan={6} className="h-20 text-center font-mono text-sm text-[#94a3b8]">
                [ 系統閒置中：目前沒有可用的物件 ]
              </TableCell>
            </TableRow>
          ) : null}
          {items.map((item) => (
            <TableRow
              key={item.bid}
              aria-selected={item.bid === selectedBid}
              className={cn(
                "cursor-pointer font-mono text-sm border-b-[#334155]/50 transition-colors group",
                item.bid === selectedBid 
                  ? "bg-[#00f0ff]/10 text-white shadow-[inset_2px_0_0_#00f0ff]" 
                  : "hover:bg-[#1a202c] text-[#cbd5e1]"
              )}
              onClick={() => onSelect?.(item.bid)}
            >
              <TableCell className="max-w-24 truncate align-middle">
                {item.bid.split("-")[0]}..
              </TableCell>
              <TableCell className="max-w-48 align-middle">
                {item.barcodeValue ? (
                  <div className="flex flex-col gap-0.5">
                    <span className="truncate font-semibold text-[#00ff66] group-hover:text-white transition-colors">{item.barcodeValue}</span>
                    <span className="text-[10px] text-[#94a3b8] tracking-widest">{item.barcodeType}</span>
                  </div>
                ) : (
                  <span className="text-[10px] tracking-widest border border-[#ef4444]/30 bg-[#ef4444]/10 text-[#ef4444] px-1.5 py-0.5 rounded">未解碼</span>
                )}
              </TableCell>
              <TableCell className="max-w-40 truncate text-[#94a3b8] hidden 2xl:table-cell align-middle">
                {item.ocrText ?? "-"}
              </TableCell>
              <TableCell className="align-middle">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-1.5 bg-[#1a202c] rounded-full overflow-hidden">
                    <div 
                      className={cn("h-full", item.confidenceScore > 0.8 ? "bg-[#00ff66]" : item.confidenceScore > 0.5 ? "bg-[#f59e0b]" : "bg-[#ef4444]")} 
                      style={{ width: `${Math.round(item.confidenceScore * 100)}%` }} 
                    />
                  </div>
                  <span className={cn(
                    "text-[10px] font-bold w-6",
                    item.confidenceScore > 0.8 ? "text-[#00ff66]" : item.confidenceScore > 0.5 ? "text-[#f59e0b]" : "text-[#ef4444]"
                  )}>
                    {Math.round(item.confidenceScore * 100)}
                  </span>
                </div>
              </TableCell>
              <TableCell className="hidden lg:table-cell align-middle">
                <ModelBadge model={item.model} />
              </TableCell>
              <TableCell className="text-right align-middle">
                <Link className="inline-flex h-6 items-center justify-center rounded border border-[#00f0ff]/30 bg-[#00f0ff]/5 px-2 text-[10px] font-bold tracking-widest text-[#00f0ff] transition-colors hover:bg-[#00f0ff] hover:text-black" href={`/objects/${item.bid}`}>
                  檢視
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
