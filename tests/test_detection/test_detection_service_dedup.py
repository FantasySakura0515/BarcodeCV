import numpy as np

from backend.detection.box_detector import BoxDetectionResult
from backend.detection.opencv_datamatrix_detector import OpenCVDataMatrixResult
from backend.detection.spatial_matcher import SpatialMatcher
from backend.services.detection_service import DetectionService


def _box(x1: int, y1: int, x2: int, y2: int) -> BoxDetectionResult:
    contour = np.array([[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]], dtype=np.int32)
    return BoxDetectionResult(bbox=(x1, y1, x2, y2), area=float((x2 - x1) * (y2 - y1)), contour=contour)


def _dm(
    content: str,
    bbox: tuple[int, int, int, int],
    confidence: float = 0.9,
    source: str = "test",
) -> OpenCVDataMatrixResult:
    return OpenCVDataMatrixResult(
        content=content,
        bbox=bbox,
        confidence=confidence,
        decoder_used="zxing-cpp",
        detection_source=source,
        scan_time_ms=5.0,
    )


def test_deduplicate_dm_detections_removes_overlapping_duplicates():
    detections = [
        _dm("DM-001", (10, 10, 60, 60), confidence=0.95),
        _dm("DM-001", (12, 12, 62, 62), confidence=0.92),
        _dm("DM-002", (200, 200, 250, 250), confidence=0.9),
    ]

    deduped = DetectionService._deduplicate_dm_detections(detections)

    assert len(deduped) == 2
    assert {item.content for item in deduped} == {"DM-001", "DM-002"}


def test_merge_box_and_dm_avoids_duplicate_entries_for_same_code():
    service = DetectionService.__new__(DetectionService)
    service._spatial_matcher = SpatialMatcher(overlap_threshold=0.1)

    boxes = [_box(0, 0, 100, 100)]
    dm_detections = [
        _dm("DM-001", (10, 10, 60, 60), confidence=0.95, source="roi"),
        _dm("DM-001", (12, 12, 62, 62), confidence=0.9, source="supplement"),
    ]

    merged = service._merge_box_and_dm(boxes, dm_detections)

    assert len(merged) == 1
    assert merged[0].content == "DM-001"
