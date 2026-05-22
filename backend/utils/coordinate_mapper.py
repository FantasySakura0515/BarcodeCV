import logging

import cv2
import numpy as np

logger = logging.getLogger("barcodecv.mapper")


class CoordinateMapper:
    """Legacy utility for cross-view coordinate mapping.

    BarcodeCV now runs on a single aggregated CamArray feed, so this helper is
    not part of the main scan flow. It is kept for experiments that still need
    a manually-specified homography between two image planes.
    """

    def __init__(self):
        self._homography: np.ndarray | None = None

    def calibrate(
        self,
        global_points: np.ndarray,
        local_points: np.ndarray,
    ) -> None:
        """Compute homography from at least 4 corresponding point pairs.

        Args:
            global_points: Nx2 array of points in Global image space.
            local_points: Nx2 array of corresponding points in Local image space.
        """
        if len(global_points) < 4 or len(local_points) < 4:
            raise ValueError("At least 4 point pairs are required for homography")

        self._homography, mask = cv2.findHomography(
            global_points.astype(np.float32),
            local_points.astype(np.float32),
            cv2.RANSAC,
            5.0,
        )
        inliers = int(mask.sum()) if mask is not None else 0
        logger.info("Homography computed with %d/%d inliers", inliers, len(global_points))

    def set_homography(self, homography: np.ndarray) -> None:
        """Set the homography matrix directly."""
        self._homography = homography.astype(np.float64)

    def map_bbox(
        self, bbox: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int] | None:
        """Map a bounding box between two calibrated image planes.

        Args:
            bbox: (x1, y1, x2, y2) in source image pixels.

        Returns:
            (x1, y1, x2, y2) in target image pixels, or None if no homography.
        """
        if self._homography is None:
            return None

        x1, y1, x2, y2 = bbox
        corners = np.array(
            [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32
        ).reshape(-1, 1, 2)

        mapped = cv2.perspectiveTransform(corners, self._homography)
        mapped = mapped.reshape(-1, 2)

        mx1 = int(mapped[:, 0].min())
        my1 = int(mapped[:, 1].min())
        mx2 = int(mapped[:, 0].max())
        my2 = int(mapped[:, 1].max())

        return (mx1, my1, mx2, my2)

    def is_calibrated(self) -> bool:
        return self._homography is not None

    def save(self, path: str) -> None:
        """Save homography matrix to file."""
        if self._homography is not None:
            np.save(path, self._homography)

    def load(self, path: str) -> None:
        """Load homography matrix from file."""
        self._homography = np.load(path)
