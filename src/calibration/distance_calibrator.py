import logging
from dataclasses import dataclass

import numpy as np

from ..camera.base import CameraSource
from ..decoding.decoder import DataMatrixDecoder
from .focus_scorer import FocusScorer

logger = logging.getLogger("barcodecv.calibration")


@dataclass
class CalibrationPoint:
    """Result of a single calibration distance test."""

    distance_mm: float
    sharpness_score: float
    decode_success: bool
    decode_time_ms: float | None


class DistanceCalibrator:
    """Determines optimal camera distance for DataMatrix decoding."""

    def __init__(
        self,
        camera: CameraSource,
        decoder: DataMatrixDecoder,
        focus_scorer: FocusScorer | None = None,
        metric: str = "laplacian",
        samples_per_distance: int = 5,
        success_threshold: float = 0.5,
    ):
        self._camera = camera
        self._decoder = decoder
        self._scorer = focus_scorer or FocusScorer()
        self._metric = metric
        self._samples = samples_per_distance
        self._success_threshold = success_threshold

    def run_sweep(self, distances_mm: list[float]) -> list[CalibrationPoint]:
        """Run calibration sweep. User manually positions camera at each distance.

        For each distance, captures multiple frames, scores sharpness,
        and attempts decode.
        """
        results = []

        for distance in distances_mm:
            input(
                f"\n>>> Position camera at {distance}mm and press Enter to capture..."
            )

            scores = []
            successes = 0
            total_decode_time = 0.0

            for i in range(self._samples):
                frame = self._camera.capture_frame()
                score = self._scorer.score(frame.image, self._metric)
                scores.append(score)

                decode_results = self._decoder.decode(frame.image)
                if any(r.success for r in decode_results):
                    successes += 1
                for r in decode_results:
                    total_decode_time += r.decode_time_ms

            avg_score = float(np.mean(scores))
            success_rate = successes / self._samples
            avg_decode_time = total_decode_time / self._samples if self._samples > 0 else None

            point = CalibrationPoint(
                distance_mm=distance,
                sharpness_score=avg_score,
                decode_success=success_rate >= self._success_threshold,
                decode_time_ms=avg_decode_time,
            )
            results.append(point)

            logger.info(
                "Distance %.0fmm: sharpness=%.1f, success_rate=%.0f%%, avg_time=%.1fms",
                distance,
                avg_score,
                success_rate * 100,
                avg_decode_time or 0,
            )

        return results

    def find_optimal_distance(self, results: list[CalibrationPoint]) -> float:
        """Find the distance with highest decode success and sharpness."""
        successful = [r for r in results if r.decode_success]

        if not successful:
            logger.warning("No distance achieved successful decoding")
            # Fall back to highest sharpness
            return max(results, key=lambda r: r.sharpness_score).distance_mm

        return max(successful, key=lambda r: r.sharpness_score).distance_mm

    def print_report(self, results: list[CalibrationPoint], optimal: float) -> None:
        """Print a human-readable calibration report."""
        print("\n=== CALIBRATION REPORT ===")
        print(f"Optimal distance: {optimal:.0f}mm")
        print()
        print(f"{'Distance':>10} {'Sharpness':>12} {'Decode OK':>12} {'Time (ms)':>12}")
        print("-" * 50)
        for r in results:
            marker = " <-- BEST" if r.distance_mm == optimal else ""
            print(
                f"{r.distance_mm:>8.0f}mm {r.sharpness_score:>12.1f} "
                f"{'YES' if r.decode_success else 'NO':>12} "
                f"{r.decode_time_ms or 0:>10.1f}ms{marker}"
            )
