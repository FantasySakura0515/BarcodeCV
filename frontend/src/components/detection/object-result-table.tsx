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
          <TableHead>Object ID (BID)</TableHead>
          <TableHead>Barcode</TableHead>
          <TableHead>OCR Text</TableHead>
          <TableHead>Confidence</TableHead>
          <TableHead>Model</TableHead>
          <TableHead className="text-right">Details</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.length === 0 ? (
          <TableRow>
            <TableCell colSpan={6} className="h-20 text-center text-sm text-muted-foreground">
              No objects available.
            </TableCell>
          </TableRow>
        ) : null}
        {items.map((item) => (
          <TableRow
            key={item.bid}
            aria-selected={item.bid === selectedBid}
            className={cn("cursor-pointer", item.bid === selectedBid && "bg-primary/5")}
            onClick={() => onSelect?.(item.bid)}
          >
            <TableCell className="max-w-32 break-all font-medium whitespace-normal">{item.bid}</TableCell>
            <TableCell className="max-w-72 whitespace-normal">
              {item.barcodeValue ? (
                <div className="space-y-1">
                  <p className="break-all font-medium">{item.barcodeValue}</p>
                  <p className="text-xs text-muted-foreground">{item.barcodeType}</p>
                </div>
              ) : (
                <Badge variant="outline">Not detected</Badge>
              )}
            </TableCell>
            <TableCell className="max-w-72 break-words whitespace-normal text-muted-foreground">{item.ocrText ?? "-"}</TableCell>
            <TableCell>{Math.round(item.confidenceScore * 100)}%</TableCell>
            <TableCell>
              <ModelBadge model={item.model} />
            </TableCell>
            <TableCell className="text-right">
              <Link className="text-sm font-medium text-primary" href={`/objects/${item.bid}`}>
                View
              </Link>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
