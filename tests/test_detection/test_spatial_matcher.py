"""Unit tests for SpatialMatcher and IoU helper."""

import numpy as np
import pytest

from backend.detection.box_detector import BoxDetectionResult
from backend.detection.spatial_matcher import (
    SpatialMatcher,
    ScanSummary,
    MatchResult,
    _compute_iou,
    _dm_center_in_box,
)
from backend.decoding.direct_scanner import ScanResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _box(x1, y1, x2, y2) -> BoxDetectionResult:
    contour = np.array([[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]])
    return BoxDetectionResult(bbox=(x1, y1, x2, y2), area=float((x2-x1)*(y2-y1)), contour=contour)


def _scan(x1, y1, x2, y2, content="DM-001") -> ScanResult:
    return ScanResult(
        content=content,
        bbox=(x1, y1, x2, y2),
        success=True,
        scanner_used="pylibdmtx",
        scan_time_ms=10.0,
    )


# ---------------------------------------------------------------------------
# _compute_iou
# ---------------------------------------------------------------------------

class TestComputeIoU:
    def test_identical_boxes(self):
        assert _compute_iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)

    def test_no_overlap(self):
        assert _compute_iou((0, 0, 10, 10), (20, 20, 30, 30)) == pytest.approx(0.0)

    def test_partial_overlap(self):
        # Two 10x10 boxes overlapping by 5x5 = 25
        # union = 100 + 100 - 25 = 175
        iou = _compute_iou((0, 0, 10, 10), (5, 5, 15, 15))
        assert iou == pytest.approx(25 / 175)

    def test_contained_box(self):
        # Inner box completely inside outer
        # intersection = 4x4=16, area_a=100, area_b=16, union=100
        iou = _compute_iou((0, 0, 10, 10), (3, 3, 7, 7))
        assert iou == pytest.approx(16 / 100)

    def test_touching_edges_no_area(self):
        # Boxes share an edge but no area overlap
        assert _compute_iou((0, 0, 10, 10), (10, 0, 20, 10)) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _dm_center_in_box
# ---------------------------------------------------------------------------

class TestDmCenterInBox:
    def test_center_inside(self):
        # DM at (10,10)-(20,20) → center (15,15); box (0,0)-(30,30) → inside
        assert _dm_center_in_box((10, 10, 20, 20), (0, 0, 30, 30)) is True

    def test_center_outside(self):
        # DM at (100,100)-(110,110) → center (105,105); box (0,0)-(30,30)
        assert _dm_center_in_box((100, 100, 110, 110), (0, 0, 30, 30)) is False

    def test_center_on_edge(self):
        # center exactly on boundary — included
        assert _dm_center_in_box((0, 0, 20, 20), (10, 0, 30, 20)) is True


# ---------------------------------------------------------------------------
# SpatialMatcher.match
# ---------------------------------------------------------------------------

class TestSpatialMatcherMatch:
    def setup_method(self):
        self.matcher = SpatialMatcher(overlap_threshold=0.1)

    def test_no_boxes_returns_empty(self):
        results = self.matcher.match([], [_scan(10, 10, 50, 50)])
        assert results == []

    def test_matched_pair(self):
        box = _box(0, 0, 100, 100)
        scan = _scan(20, 20, 60, 60)  # clearly inside box, high IoU
        results = self.matcher.match([box], [scan])
        assert len(results) == 1
        assert results[0].status == "matched"
        assert results[0].scan_result is scan
        assert results[0].overlap_ratio > 0

    def test_missing_datamatrix(self):
        box = _box(0, 0, 100, 100)
        scan = _scan(200, 200, 250, 250)  # completely outside box
        results = self.matcher.match([box], [scan])
        assert len(results) == 1
        assert results[0].status == "missing_datamatrix"
        assert results[0].scan_result is None
        assert results[0].overlap_ratio == 0.0

    def test_no_scan_results_all_missing(self):
        boxes = [_box(0, 0, 100, 100), _box(200, 0, 300, 100)]
        results = self.matcher.match(boxes, [])
        assert all(r.status == "missing_datamatrix" for r in results)
        assert len(results) == 2

    def test_greedy_one_scan_per_box(self):
        """One DataMatrix should only be assigned to one box."""
        box1 = _box(0, 0, 100, 100)
        box2 = _box(50, 0, 150, 100)  # overlaps with box1
        scan = _scan(40, 10, 80, 50, content="DM-001")  # overlaps both
        results = self.matcher.match([box1, box2], [scan])
        matched = [r for r in results if r.status == "matched"]
        missing = [r for r in results if r.status == "missing_datamatrix"]
        assert len(matched) == 1
        assert len(missing) == 1

    def test_multiple_boxes_multiple_scans(self):
        box1 = _box(0, 0, 100, 100)
        box2 = _box(200, 0, 300, 100)
        scan1 = _scan(10, 10, 80, 80, content="DM-001")
        scan2 = _scan(210, 10, 280, 80, content="DM-002")
        results = self.matcher.match([box1, box2], [scan1, scan2])
        assert all(r.status == "matched" for r in results)
        contents = {r.scan_result.content for r in results}
        assert contents == {"DM-001", "DM-002"}

    def test_center_fallback_matches_when_iou_below_threshold(self):
        """DataMatrix center inside box should match even if IoU < threshold."""
        matcher = SpatialMatcher(overlap_threshold=0.9)  # very strict IoU
        box = _box(0, 0, 200, 200)
        # DM slightly larger than box so IoU is low but center (100,100) is inside
        scan = _scan(-50, -50, 250, 250, content="DM-LARGE")
        results = matcher.match([box], [scan])
        assert results[0].status == "matched"

    def test_only_successful_scans_are_used(self):
        """Failed scans (success=False) should not be matched."""
        box = _box(0, 0, 100, 100)
        failed = ScanResult(
            content=None, bbox=(10, 10, 80, 80), success=False,
            scanner_used="pylibdmtx", scan_time_ms=5.0,
        )
        results = self.matcher.match([box], [failed])
        assert results[0].status == "missing_datamatrix"


# ---------------------------------------------------------------------------
# SpatialMatcher.summarize
# ---------------------------------------------------------------------------

class TestSpatialMatcherSummarize:
    def setup_method(self):
        self.matcher = SpatialMatcher()

    def test_summarize_all_matched(self):
        box = _box(0, 0, 100, 100)
        scan = _scan(10, 10, 80, 80)
        match_results = self.matcher.match([box], [scan])
        summary = self.matcher.summarize(match_results, total_datamatrix=1)
        assert summary.total_boxes == 1
        assert summary.total_datamatrix == 1
        assert len(summary.matched) == 1
        assert len(summary.missing) == 0
        assert summary.success_rate == pytest.approx(1.0)

    def test_summarize_all_missing(self):
        box = _box(0, 0, 100, 100)
        match_results = self.matcher.match([box], [])
        summary = self.matcher.summarize(match_results, total_datamatrix=0)
        assert summary.total_boxes == 1
        assert len(summary.missing) == 1
        assert summary.success_rate == pytest.approx(0.0)

    def test_summarize_empty(self):
        summary = self.matcher.summarize([], total_datamatrix=0)
        assert summary.success_rate == pytest.approx(0.0)
        assert summary.total_boxes == 0

    def test_from_config_default(self):
        matcher = SpatialMatcher.from_config({})
        assert matcher._threshold == pytest.approx(0.3)

    def test_from_config_custom(self):
        matcher = SpatialMatcher.from_config({"spatial_matching": {"overlap_threshold": 0.5}})
        assert matcher._threshold == pytest.approx(0.5)
