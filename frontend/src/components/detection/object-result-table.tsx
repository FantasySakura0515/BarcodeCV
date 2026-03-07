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
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>物件編號 (BID)</TableHead>
          <TableHead>條碼</TableHead>
          <TableHead>OCR 文字</TableHead>
          <TableHead>信心度</TableHead>
          <TableHead>使用模型</TableHead>
          <TableHead className="text-right">詳細資訊</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow
            key={item.bid}
            className={cn("cursor-pointer", item.bid === selectedBid && "bg-primary/5")}
            onClick={() => onSelect?.(item.bid)}
          >
            <TableCell className="max-w-32 font-medium whitespace-normal break-all">{item.bid}</TableCell>
            <TableCell className="max-w-72 whitespace-normal">
              {item.barcodeValue ? (
                <div className="space-y-1">
                  <p className="font-medium break-all">{item.barcodeValue}</p>
                  <p className="text-xs text-muted-foreground">{item.barcodeType}</p>
                </div>
              ) : (
                <Badge variant="outline">N/A</Badge>
              )}
            </TableCell>
            <TableCell className="max-w-72 whitespace-normal break-words text-muted-foreground">{item.ocrText ?? "-"}</TableCell>
            <TableCell>{Math.round(item.confidenceScore * 100)}%</TableCell>
            <TableCell><ModelBadge model={item.model} /></TableCell>
            <TableCell className="text-right">
              <Link className="text-sm font-medium text-primary" href={`/objects/${item.bid}`}>
                查看
              </Link>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
