import cv2
import numpy as np


def preprocess_for_detection(
    image: np.ndarray,
    apply_clahe: bool = True,
    clahe_clip_limit: float = 2.0,
) -> np.ndarray:
    """Preprocess an image before YOLO detection.

    Applies optional CLAHE for better contrast in poor lighting.
    YOLO handles its own resizing, so we don't resize here.
    """
    result = image.copy()

    if apply_clahe:
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        l_channel, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        result = cv2.merge([l_channel, a, b])
        result = cv2.cvtColor(result, cv2.COLOR_LAB2BGR)

    return result
