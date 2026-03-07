"""Generate synthetic training images with boxes and DataMatrix labels.

Each image simulates a top-down view of a flat surface with several boxes.
Each box may or may not have a DataMatrix label on it.

Classes:
    0: box         — rectangular package on the surface
    1: datamatrix  — DataMatrix code on top of a box

Usage:
    python -m training.prepare_dataset --num-images 2000 --output-dir training/data
"""

import argparse
import os
import random
import string

import cv2
import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# DataMatrix encoding
# ---------------------------------------------------------------------------

def generate_random_content(min_len: int = 4, max_len: int = 30) -> str:
    length = random.randint(min_len, max_len)
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def encode_datamatrix(content: str) -> np.ndarray | None:
    try:
        from pylibdmtx.pylibdmtx import encode
        encoded = encode(content.encode("utf-8"))
        img = Image.frombytes("RGB", (encoded.width, encoded.height), encoded.pixels)
        return np.array(img)
    except Exception as e:
        print(f"Warning: Failed to encode '{content}': {e}")
        return None


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------

def create_random_background(width: int, height: int) -> np.ndarray:
    bg_type = random.choice(["solid", "gradient", "noise", "texture"])
    if bg_type == "solid":
        color = [random.randint(150, 255) for _ in range(3)]
        bg = np.full((height, width, 3), color, dtype=np.uint8)
    elif bg_type == "gradient":
        bg = np.zeros((height, width, 3), dtype=np.uint8)
        for i in range(3):
            start, end = random.randint(150, 255), random.randint(150, 255)
            bg[:, :, i] = np.linspace(start, end, width).astype(np.uint8)
    elif bg_type == "noise":
        bg = np.random.randint(180, 255, (height, width, 3), dtype=np.uint8)
    else:
        bg = np.random.randint(200, 255, (height, width, 3), dtype=np.uint8)
        bg = cv2.GaussianBlur(bg, (15, 15), 0)
    return bg


# ---------------------------------------------------------------------------
# Box + DataMatrix placement
# ---------------------------------------------------------------------------

def random_box_color() -> tuple[int, int, int]:
    """Generate a random box-top color (cardboard-ish tones)."""
    style = random.choice(["brown", "white", "gray", "colored"])
    if style == "brown":
        return (random.randint(140, 190), random.randint(110, 150), random.randint(70, 110))
    elif style == "white":
        v = random.randint(220, 250)
        return (v, v, v)
    elif style == "gray":
        v = random.randint(140, 200)
        return (v, v, v)
    else:
        return (random.randint(80, 220), random.randint(80, 220), random.randint(80, 220))


def place_box_with_dm(
    bg: np.ndarray,
    box_w: int,
    box_h: int,
    x: int,
    y: int,
    has_dm: bool,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int] | None]:
    """Draw a box on bg at (x, y). Optionally place a DataMatrix on it.

    Returns (box_bbox, dm_bbox_or_None).
    """
    color = random_box_color()
    cv2.rectangle(bg, (x, y), (x + box_w, y + box_h), color, -1)

    # Subtle border
    border_color = tuple(max(0, c - 40) for c in color)
    cv2.rectangle(bg, (x, y), (x + box_w, y + box_h), border_color, 2)

    box_bbox = (x, y, x + box_w, y + box_h)
    dm_bbox = None

    if has_dm:
        content = generate_random_content()
        dm_img = encode_datamatrix(content)
        if dm_img is not None:
            # Scale DM to fit inside box (20%-50% of box width)
            dm_scale = random.uniform(0.2, 0.5)
            dm_w = int(box_w * dm_scale)
            dm_h = int(dm_w * dm_img.shape[0] / dm_img.shape[1])
            if dm_w >= 8 and dm_h >= 8:
                dm_resized = cv2.resize(dm_img, (dm_w, dm_h), interpolation=cv2.INTER_AREA)

                # Random position within the box with margin
                margin = 4
                max_dx = box_w - dm_w - margin * 2
                max_dy = box_h - dm_h - margin * 2
                if max_dx > 0 and max_dy > 0:
                    dx = x + margin + random.randint(0, max_dx)
                    dy = y + margin + random.randint(0, max_dy)
                    bg[dy:dy + dm_h, dx:dx + dm_w] = dm_resized
                    dm_bbox = (dx, dy, dx + dm_w, dy + dm_h)

    return box_bbox, dm_bbox


def try_place_boxes(
    bg: np.ndarray,
    num_boxes: int,
    min_box_frac: float = 0.08,
    max_box_frac: float = 0.25,
    dm_probability: float = 0.8,
) -> list[tuple[tuple[int, int, int, int], tuple[int, int, int, int] | None]]:
    """Place non-overlapping boxes on the background.

    Returns list of (box_bbox, dm_bbox_or_None).
    """
    bg_h, bg_w = bg.shape[:2]
    placed = []
    occupied = []

    for _ in range(num_boxes * 5):  # extra attempts for placement
        if len(placed) >= num_boxes:
            break

        box_w = int(bg_w * random.uniform(min_box_frac, max_box_frac))
        box_h = int(box_w * random.uniform(0.6, 1.5))  # aspect ratio variation

        if box_w + 4 > bg_w or box_h + 4 > bg_h:
            continue

        x = random.randint(2, bg_w - box_w - 2)
        y = random.randint(2, bg_h - box_h - 2)
        candidate = (x, y, x + box_w, y + box_h)

        # Check overlap with existing boxes
        overlap = False
        for occ in occupied:
            if not (candidate[2] < occ[0] or candidate[0] > occ[2]
                    or candidate[3] < occ[1] or candidate[1] > occ[3]):
                overlap = True
                break
        if overlap:
            continue

        has_dm = random.random() < dm_probability
        box_bbox, dm_bbox = place_box_with_dm(bg, box_w, box_h, x, y, has_dm)
        placed.append((box_bbox, dm_bbox))
        occupied.append(candidate)

    return placed


# ---------------------------------------------------------------------------
# Augmentations
# ---------------------------------------------------------------------------

def apply_augmentations(image: np.ndarray) -> np.ndarray:
    if random.random() < 0.5:
        factor = random.uniform(0.7, 1.3)
        image = np.clip(image * factor, 0, 255).astype(np.uint8)
    if random.random() < 0.3:
        ksize = random.choice([3, 5])
        image = cv2.GaussianBlur(image, (ksize, ksize), 0)
    if random.random() < 0.3:
        noise = np.random.normal(0, random.uniform(5, 15), image.shape).astype(np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return image


# ---------------------------------------------------------------------------
# YOLO format
# ---------------------------------------------------------------------------

def bbox_to_yolo(class_id: int, bbox: tuple[int, int, int, int], img_w: int, img_h: int) -> str:
    x1, y1, x2, y2 = bbox
    x_center = (x1 + x2) / 2.0 / img_w
    y_center = (y1 + y2) / 2.0 / img_h
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h
    return f"{class_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------

def generate_dataset(
    num_images: int,
    output_dir: str,
    img_width: int = 640,
    img_height: int = 640,
    max_boxes_per_image: int = 8,
    dm_probability: float = 0.8,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
):
    splits = {
        "train": int(num_images * train_ratio),
        "val": int(num_images * val_ratio),
        "test": num_images - int(num_images * train_ratio) - int(num_images * val_ratio),
    }

    for split_name, count in splits.items():
        img_dir = os.path.join(output_dir, "images", split_name)
        lbl_dir = os.path.join(output_dir, "labels", split_name)
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)

        for i in range(count):
            bg = create_random_background(img_width, img_height)
            num_boxes = random.randint(1, max_boxes_per_image)
            results = try_place_boxes(bg, num_boxes, dm_probability=dm_probability)

            annotations = []
            for box_bbox, dm_bbox in results:
                annotations.append(bbox_to_yolo(0, box_bbox, img_width, img_height))
                if dm_bbox is not None:
                    annotations.append(bbox_to_yolo(1, dm_bbox, img_width, img_height))

            bg = apply_augmentations(bg)

            filename = f"scene_{split_name}_{i:05d}"
            cv2.imwrite(os.path.join(img_dir, f"{filename}.jpg"), bg)
            with open(os.path.join(lbl_dir, f"{filename}.txt"), "w") as f:
                f.write("\n".join(annotations))

            if (i + 1) % 100 == 0:
                print(f"  [{split_name}] {i + 1}/{count} images generated")

        print(f"  [{split_name}] Done: {count} images")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic box + DataMatrix dataset")
    parser.add_argument("--num-images", type=int, default=2000)
    parser.add_argument("--output-dir", type=str, default="training/data")
    parser.add_argument("--img-size", type=int, default=640)
    parser.add_argument("--max-boxes", type=int, default=8)
    parser.add_argument("--dm-probability", type=float, default=0.8,
                        help="Probability each box has a DataMatrix label")
    args = parser.parse_args()

    print(f"Generating {args.num_images} synthetic images (2 classes: box, datamatrix)...")
    generate_dataset(
        num_images=args.num_images,
        output_dir=args.output_dir,
        img_width=args.img_size,
        img_height=args.img_size,
        max_boxes_per_image=args.max_boxes,
        dm_probability=args.dm_probability,
    )
    print("Dataset generation complete!")


if __name__ == "__main__":
    main()
