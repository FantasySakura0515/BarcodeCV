import cv2
import numpy as np


def crop_region(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """Crop a region from an image given (x1, y1, x2, y2) bounding box."""
    x1, y1, x2, y2 = bbox
    h, w = image.shape[:2]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)
    return image[y1:y2, x1:x2]


def resize_with_padding(
    image: np.ndarray, target_size: tuple[int, int]
) -> np.ndarray:
    """Resize image to target size while maintaining aspect ratio, padding with black."""
    th, tw = target_size
    h, w = image.shape[:2]
    scale = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((th, tw, 3), dtype=np.uint8)
    y_offset = (th - nh) // 2
    x_offset = (tw - nw) // 2
    canvas[y_offset : y_offset + nh, x_offset : x_offset + nw] = resized
    return canvas


def enhance_contrast(image: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Apply CLAHE contrast enhancement."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return clahe.apply(gray)


def sharpen(image: np.ndarray) -> np.ndarray:
    """Apply sharpening filter."""
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    return cv2.filter2D(image, -1, kernel)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert BGR image to grayscale."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
