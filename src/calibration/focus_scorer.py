import cv2
import numpy as np


class FocusScorer:
    """Image sharpness scoring for calibration."""

    @staticmethod
    def laplacian_variance(image: np.ndarray) -> float:
        """Laplacian variance sharpness metric. Higher = sharper."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def tenengrad(image: np.ndarray) -> float:
        """Sobel gradient sharpness metric. Higher = sharper."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        return float(np.mean(gx**2 + gy**2))

    def score(self, image: np.ndarray, metric: str = "laplacian") -> float:
        """Score image sharpness using the specified metric."""
        if metric == "laplacian":
            return self.laplacian_variance(image)
        elif metric == "tenengrad":
            return self.tenengrad(image)
        else:
            raise ValueError(f"Unknown metric: {metric}")
