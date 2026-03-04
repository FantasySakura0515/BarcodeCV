"""Generate synthetic DataMatrix training images with YOLO-format annotations.

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


def generate_random_content(min_len: int = 4, max_len: int = 30) -> str:
    """Generate random alphanumeric string for DataMatrix encoding."""
    length = random.randint(min_len, max_len)
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def encode_datamatrix(content: str) -> np.ndarray | None:
    """Encode content as a DataMatrix image using pylibdmtx."""
    try:
        from pylibdmtx.pylibdmtx import encode

        encoded = encode(content.encode("utf-8"))
        img = Image.frombytes("RGB", (encoded.width, encoded.height), encoded.pixels)
        return np.array(img)
    except Exception as e:
        print(f"Warning: Failed to encode '{content}': {e}")
        return None


def create_random_background(width: int, height: int) -> np.ndarray:
    """Create a random background image."""
    bg_type = random.choice(["solid", "gradient", "noise", "texture"])

    if bg_type == "solid":
        color = [random.randint(150, 255) for _ in range(3)]
        bg = np.full((height, width, 3), color, dtype=np.uint8)
    elif bg_type == "gradient":
        bg = np.zeros((height, width, 3), dtype=np.uint8)
        for i in range(3):
            start = random.randint(150, 255)
            end = random.randint(150, 255)
            gradient = np.linspace(start, end, width).astype(np.uint8)
            bg[:, :, i] = gradient
    elif bg_type == "noise":
        bg = np.random.randint(180, 255, (height, width, 3), dtype=np.uint8)
    else:  # texture
        bg = np.random.randint(200, 255, (height, width, 3), dtype=np.uint8)
        bg = cv2.GaussianBlur(bg, (15, 15), 0)

    return bg


def place_datamatrix(
    bg: np.ndarray,
    dm_image: np.ndarray,
    min_scale: float = 0.05,
    max_scale: float = 0.25,
) -> tuple[int, int, int, int] | None:
    """Place a DataMatrix on the background at random position/scale.

    Returns (x1, y1, x2, y2) bounding box or None if placement failed.
    """
    bg_h, bg_w = bg.shape[:2]
    scale = random.uniform(min_scale, max_scale)
    target_w = int(bg_w * scale)
    target_h = int(target_w * dm_image.shape[0] / dm_image.shape[1])

    if target_w < 10 or target_h < 10:
        return None

    resized = cv2.resize(dm_image, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # Random rotation
    angle = random.uniform(-15, 15)
    center = (target_w // 2, target_h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(target_h * sin_a + target_w * cos_a)
    new_h = int(target_h * cos_a + target_w * sin_a)
    M[0, 2] += (new_w - target_w) / 2
    M[1, 2] += (new_h - target_h) / 2
    rotated = cv2.warpAffine(resized, M, (new_w, new_h), borderValue=(255, 255, 255))

    # Random position
    max_x = bg_w - new_w
    max_y = bg_h - new_h
    if max_x < 0 or max_y < 0:
        return None

    x = random.randint(0, max_x)
    y = random.randint(0, max_y)

    # Place on background
    bg[y : y + new_h, x : x + new_w] = rotated

    return (x, y, x + new_w, y + new_h)


def apply_augmentations(image: np.ndarray) -> np.ndarray:
    """Apply random augmentations to the full scene."""
    # Random brightness
    if random.random() < 0.5:
        factor = random.uniform(0.7, 1.3)
        image = np.clip(image * factor, 0, 255).astype(np.uint8)

    # Random Gaussian blur
    if random.random() < 0.3:
        ksize = random.choice([3, 5])
        image = cv2.GaussianBlur(image, (ksize, ksize), 0)

    # Random noise
    if random.random() < 0.3:
        noise = np.random.normal(0, random.uniform(5, 15), image.shape).astype(np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return image


def bbox_to_yolo(bbox: tuple[int, int, int, int], img_w: int, img_h: int) -> str:
    """Convert (x1, y1, x2, y2) to YOLO format: class x_center y_center width height (normalized)."""
    x1, y1, x2, y2 = bbox
    x_center = (x1 + x2) / 2.0 / img_w
    y_center = (y1 + y2) / 2.0 / img_h
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h
    return f"0 {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"


def generate_dataset(
    num_images: int,
    output_dir: str,
    img_width: int = 640,
    img_height: int = 640,
    max_codes_per_image: int = 5,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
):
    """Generate synthetic DataMatrix training dataset."""
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

        generated = 0
        attempts = 0
        while generated < count and attempts < count * 3:
            attempts += 1
            bg = create_random_background(img_width, img_height)
            num_codes = random.randint(1, max_codes_per_image)
            annotations = []

            for _ in range(num_codes):
                content = generate_random_content()
                dm_img = encode_datamatrix(content)
                if dm_img is None:
                    continue

                bbox = place_datamatrix(bg, dm_img)
                if bbox is not None:
                    yolo_line = bbox_to_yolo(bbox, img_width, img_height)
                    annotations.append(yolo_line)

            if not annotations:
                continue

            bg = apply_augmentations(bg)

            filename = f"dm_{split_name}_{generated:05d}"
            cv2.imwrite(os.path.join(img_dir, f"{filename}.jpg"), bg)
            with open(os.path.join(lbl_dir, f"{filename}.txt"), "w") as f:
                f.write("\n".join(annotations))

            generated += 1
            if generated % 100 == 0:
                print(f"  [{split_name}] {generated}/{count} images generated")

        print(f"  [{split_name}] Done: {generated} images")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic DataMatrix dataset")
    parser.add_argument("--num-images", type=int, default=2000)
    parser.add_argument("--output-dir", type=str, default="training/data")
    parser.add_argument("--img-size", type=int, default=640)
    parser.add_argument("--max-codes", type=int, default=5)
    args = parser.parse_args()

    print(f"Generating {args.num_images} synthetic images...")
    generate_dataset(
        num_images=args.num_images,
        output_dir=args.output_dir,
        img_width=args.img_size,
        img_height=args.img_size,
        max_codes_per_image=args.max_codes,
    )
    print("Dataset generation complete!")


if __name__ == "__main__":
    main()
