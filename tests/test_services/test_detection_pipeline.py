import numpy as np

from backend.detection.opencv_datamatrix_detector import OpenCVDataMatrixResult
from backend.services.detection_pipeline import DetectionPipeline


def build_pipeline() -> DetectionPipeline:
    return DetectionPipeline(
        detector=None,
        fast_detector=None,
        box_detection_enabled=False,
        box_detector=None,
        spatial_matcher=None,
        min_result_confidence=0.6,
        square_ratio_max=1.35,
        square_candidate_limit=180,
        supplement_when_mismatch=True,
    )


def test_apply_confidence_filter_keeps_box_only_placeholders():
    pipeline = build_pipeline()
    detections = [
        OpenCVDataMatrixResult("DM-001", (0, 0, 10, 10), 0.95, "zxing", "full-frame", 1.2),
        OpenCVDataMatrixResult("DM-LOW", (8, 8, 16, 16), 0.25, "zxing", "full-frame", 1.0),
        OpenCVDataMatrixResult("", (20, 20, 30, 30), 0.35, "box-detector", "box-only", 0.0),
        OpenCVDataMatrixResult("", (20, 20, 30, 30), 0.25, "zxing", "full-frame", 1.1),
    ]

    filtered = pipeline.apply_confidence_filter(detections)

    assert len(filtered) == 2
    assert filtered[0].content == "DM-001"
    assert filtered[1].detection_source == "box-only"


def test_draw_object_overlays_returns_annotated_copy():
    pipeline = build_pipeline()
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    detections = [
        OpenCVDataMatrixResult("DM-001", (10, 10, 40, 40), 0.95, "zxing", "full-frame", 1.2),
    ]

    annotated = pipeline.draw_object_overlays(image, detections)

    assert annotated.shape == image.shape
    assert not np.array_equal(annotated, image)
