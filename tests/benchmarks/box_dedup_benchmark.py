"""Benchmark for BoxDetector dedup strategy.

Compares:
- legacy dedup (prefer larger boxes by area desc + IoU>0.5)
- current dedup (prefer tighter boxes with overlap/containment rules)

Run:
    ./.venv/Scripts/python.exe tests/benchmarks/box_dedup_benchmark.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.detection.box_detector import BoxDetectionResult, BoxDetector


def legacy_dedup(results: list[BoxDetectionResult]) -> list[BoxDetectionResult]:
    deduped: list[BoxDetectionResult] = []
    for item in sorted(results, key=lambda r: r.area, reverse=True):
        if any(BoxDetector._iou(item.bbox, existing.bbox) > 0.5 for existing in deduped):
            continue
        deduped.append(item)
    return deduped


def make_candidates() -> list[BoxDetectionResult]:
    # 3 true boxes, each with an outer+inner duplicate contour + slight jitter boxes.
    boxes = [
        ((50, 50, 180, 160), (40, 40, 190, 170), (55, 55, 175, 155)),
        ((300, 50, 430, 160), (290, 40, 440, 170), (305, 55, 425, 155)),
        ((50, 280, 180, 390), (40, 270, 190, 400), (55, 285, 175, 385)),
    ]
    out: list[BoxDetectionResult] = []
    for tight, outer, jitter in boxes:
        for bbox in (outer, tight, jitter):
            x1, y1, x2, y2 = bbox
            area = float((x2 - x1) * (y2 - y1))
            out.append(BoxDetectionResult(bbox=bbox, area=area, contour=[]))
    return out


def main() -> None:
    detector = BoxDetector(min_area=1, max_area=999999)
    candidates = make_candidates()

    rounds = 2000

    t0 = time.perf_counter()
    legacy = None
    for _ in range(rounds):
        legacy = legacy_dedup(candidates)
    legacy_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    current = None
    for _ in range(rounds):
        current = detector._deduplicate(candidates)
    current_ms = (time.perf_counter() - t1) * 1000

    assert legacy is not None and current is not None

    # Evaluate "tightness" as total area; lower is tighter.
    legacy_area = sum((b.bbox[2] - b.bbox[0]) * (b.bbox[3] - b.bbox[1]) for b in legacy)
    current_area = sum((b.bbox[2] - b.bbox[0]) * (b.bbox[3] - b.bbox[1]) for b in current)

    print(f"legacy_count={len(legacy)} current_count={len(current)}")
    print(f"legacy_total_area={legacy_area} current_total_area={current_area}")
    print(f"legacy_time_ms={legacy_ms:.2f} current_time_ms={current_ms:.2f} rounds={rounds}")


if __name__ == "__main__":
    main()
