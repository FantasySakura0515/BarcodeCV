"""Spatial matching between detected boxes and scanned DataMatrix codes.

For each box detected on the surface, determines whether a DataMatrix
code was found within it. Boxes without a matching DataMatrix are flagged
so the user can reposition them.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

from ..decoding.direct_scanner import ScanResult
from .box_detector import BoxDetectionResult

logger = logging.getLogger("barcodecv.spatial_matcher")


@dataclass
class MatchResult:
    """Pairing of one detected box with its DataMatrix scan result."""

    box: BoxDetectionResult
    scan_result: ScanResult | None   # None if no DataMatrix found for this box
    status: str                      # "matched" | "missing_datamatrix"
    overlap_ratio: float             # IoU between box bbox and datamatrix bbox


@dataclass
class ScanSummary:
    """High-level summary of a complete scan cycle."""

    matched: list[MatchResult] = field(default_factory=list)
    missing: list[MatchResult] = field(default_factory=list)
    total_boxes: int = 0
    total_datamatrix: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_boxes == 0:
            return 0.0
        return len(self.matched) / self.total_boxes


def _compute_iou(
    bbox_a: tuple[int, int, int, int],
    bbox_b: tuple[int, int, int, int],
) -> float:
    """Compute Intersection over Union (IoU) between two bounding boxes."""
    ax1, ay1, ax2, ay2 = bbox_a
    bx1, by1, bx2, by2 = bbox_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    if inter_area == 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union_area = area_a + area_b - inter_area

    return inter_area / union_area if union_area > 0 else 0.0


def _dm_center_in_box(
    dm_bbox: tuple[int, int, int, int],
    box_bbox: tuple[int, int, int, int],
) -> bool:
    """Check if the center of the DataMatrix bbox lies inside the box bbox."""
    dx1, dy1, dx2, dy2 = dm_bbox
    bx1, by1, bx2, by2 = box_bbox
    cx = (dx1 + dx2) / 2
    cy = (dy1 + dy2) / 2
    return bx1 <= cx <= bx2 and by1 <= cy <= by2


class SpatialMatcher:
    """Match DataMatrix scan results to detected boxes by spatial proximity.

    Matching strategy:
    1. For each (box, datamatrix) pair, compute IoU.
    2. Also accept if the DataMatrix center point falls inside the box bbox
       (handles cases where the DataMatrix is larger than expected IoU threshold).
    3. Each DataMatrix is assigned to at most one box (greedy: highest IoU first).
    4. Boxes without a matched DataMatrix are marked "missing_datamatrix".
    """

    def __init__(self, overlap_threshold: float = 0.3):
        self._threshold = overlap_threshold

    def match(
        self,
        boxes: list[BoxDetectionResult],
        scan_results: list[ScanResult],
    ) -> list[MatchResult]:
        """Match scan results to boxes. Returns one MatchResult per box."""
        if not boxes:
            return []

        successful_scans = [r for r in scan_results if r.success]

        # Build IoU matrix: rows=boxes, cols=scan_results
        iou_matrix = np.zeros((len(boxes), len(successful_scans)), dtype=float)
        center_matrix = np.zeros((len(boxes), len(successful_scans)), dtype=bool)

        for i, box in enumerate(boxes):
            for j, scan in enumerate(successful_scans):
                iou_matrix[i, j] = _compute_iou(box.bbox, scan.bbox)
                center_matrix[i, j] = _dm_center_in_box(scan.bbox, box.bbox)

        # Greedy matching: assign highest-IoU pairs first
        assigned_scans: set[int] = set()
        box_to_scan: dict[int, tuple[int, float]] = {}  # box_idx → (scan_idx, iou)

        # Sort all (box, scan) pairs by IoU descending
        pairs = [
            (iou_matrix[i, j], i, j)
            for i in range(len(boxes))
            for j in range(len(successful_scans))
            if iou_matrix[i, j] >= self._threshold or center_matrix[i, j]
        ]
        pairs.sort(reverse=True)

        for iou, box_idx, scan_idx in pairs:
            if box_idx in box_to_scan:
                continue  # Box already matched
            if scan_idx in assigned_scans:
                continue  # Scan already assigned
            box_to_scan[box_idx] = (scan_idx, iou)
            assigned_scans.add(scan_idx)

        # Build MatchResult list
        results = []
        for i, box in enumerate(boxes):
            if i in box_to_scan:
                scan_idx, iou = box_to_scan[i]
                results.append(
                    MatchResult(
                        box=box,
                        scan_result=successful_scans[scan_idx],
                        status="matched",
                        overlap_ratio=iou,
                    )
                )
            else:
                results.append(
                    MatchResult(
                        box=box,
                        scan_result=None,
                        status="missing_datamatrix",
                        overlap_ratio=0.0,
                    )
                )

        matched = sum(1 for r in results if r.status == "matched")
        missing = len(results) - matched
        logger.info(
            "Spatial matching: %d boxes → %d matched, %d missing DataMatrix",
            len(boxes),
            matched,
            missing,
        )
        return results

    def summarize(
        self,
        match_results: list[MatchResult],
        total_datamatrix: int,
    ) -> ScanSummary:
        """Build a ScanSummary from match results."""
        matched = [r for r in match_results if r.status == "matched"]
        missing = [r for r in match_results if r.status == "missing_datamatrix"]
        return ScanSummary(
            matched=matched,
            missing=missing,
            total_boxes=len(match_results),
            total_datamatrix=total_datamatrix,
        )

    @staticmethod
    def from_config(config: dict) -> "SpatialMatcher":
        cfg = config.get("spatial_matching", {})
        return SpatialMatcher(
            overlap_threshold=cfg.get("overlap_threshold", 0.3)
        )
