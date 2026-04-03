"""Generate synthetic DataMatrix recognition dataset for CRNN training.

Produces (cropped DataMatrix image, content label) pairs.

Usage::

    python -m training.prepare_recognition_dataset \\
        --num-images 5000 \\
        --output-dir training/data/recognition

Output structure::

    training/data/recognition/
    ├── images/
    │   ├── train/  (70 %)
    │   └── val/    (30 %)
    ├── labels_train.txt    # "filename\\tcontent" (one per line)
    └── labels_val.txt

Requirements (training machine only)::

    pip install pylibdmtx albumentations Pillow opencv-python

Note:
    ``pylibdmtx.pylibdmtx.encode`` is used here only as a *synthetic-data
    generator* — it is NOT imported at inference time.  The recognition
    library (``pylibdmtx.pylibdmtx.decode``) is never called by this script.
"""

import argparse
import os
import random
import string

import cv2
import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def generate_random_content(min_len: int = 3, max_len: int = 28) -> str:
    """Random alphanumeric string (typical DataMatrix payload)."""
    length = random.randint(min_len, max_len)
    chars = string.ascii_uppercase + string.digits + "-./:"
    return "".join(random.choices(chars, k=length))


def encode_datamatrix(content: str) -> np.ndarray | None:
    """Render *content* as a DataMatrix image using pylibdmtx.encode.

    This function uses the *encoder* half of pylibdmtx — it generates
    barcode images for training data and is not used at inference time.

    Returns:
        RGB uint8 ndarray, or ``None`` if encoding fails.
    """
    try:
        from PIL import Image
        from pylibdmtx.pylibdmtx import encode  # type: ignore[import]

        encoded = encode(content.encode("utf-8"))
        img = Image.frombytes("RGB", (encoded.width, encoded.height), encoded.pixels)
        return np.array(img)
    except Exception as exc:
        print(f"Warning: failed to encode '{content}': {exc}")
        return None


def augment_crop(image: np.ndarray) -> np.ndarray:
    """Apply random photometric + geometric augmentation to a single crop."""
    try:
        import albumentations as A  # type: ignore[import]

        transform = A.Compose(
            [
                A.RandomBrightnessContrast(brightness_limit=0.3, contrast_limit=0.3, p=0.5),
                A.GaussNoise(var_limit=(10.0, 50.0), p=0.4),
                A.GaussianBlur(blur_limit=(3, 5), p=0.3),
                A.Perspective(scale=(0.02, 0.08), p=0.4),
                A.Rotate(limit=10, border_mode=cv2.BORDER_REPLICATE, p=0.5),
                A.GridDistortion(num_steps=3, distort_limit=0.1, p=0.2),
            ]
        )
        return transform(image=image)["image"]
    except ImportError:
        # Fall back to basic NumPy augmentation if albumentations is absent
        if random.random() < 0.5:
            factor = random.uniform(0.7, 1.3)
            image = np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)
        if random.random() < 0.3:
            ksize = random.choice([3, 5])
            image = cv2.GaussianBlur(image, (ksize, ksize), 0)
        return image


def create_recognition_sample(
    content: str,
    output_size: tuple[int, int] = (256, 32),
    augment: bool = True,
) -> np.ndarray | None:
    """Create a single (augmented) CRNN training image for *content*.

    Args:
        content:     String to encode.
        output_size: (width, height) of the resized output image.
        augment:     Whether to apply random augmentation.

    Returns:
        Grayscale uint8 ndarray of shape ``(height, width)``, or ``None``.
    """
    dm_img = encode_datamatrix(content)
    if dm_img is None:
        return None

    # Augment the raw DataMatrix image before resizing
    if augment:
        dm_img = augment_crop(dm_img)

    # Convert to grayscale and resize to fixed CRNN input size (W × H)
    gray = cv2.cvtColor(dm_img, cv2.COLOR_RGB2GRAY)
    resized = cv2.resize(gray, output_size, interpolation=cv2.INTER_AREA)
    return resized


# ──────────────────────────────────────────────────────────────────────────────
# Dataset generation
# ──────────────────────────────────────────────────────────────────────────────


def generate_dataset(
    num_images: int,
    output_dir: str,
    img_width: int = 256,
    img_height: int = 32,
    train_ratio: float = 0.7,
) -> None:
    """Generate the full recognition dataset.

    Args:
        num_images:  Total number of images to generate.
        output_dir:  Root output directory.
        img_width:   CRNN input width (must match ``training/models/crnn.py``).
        img_height:  CRNN input height.
        train_ratio: Fraction of images used for training (rest → validation).
    """
    n_train = int(num_images * train_ratio)
    n_val = num_images - n_train

    for split, count in [("train", n_train), ("val", n_val)]:
        img_dir = os.path.join(output_dir, "images", split)
        os.makedirs(img_dir, exist_ok=True)

        label_lines: list[str] = []
        generated = 0
        attempts = 0

        while generated < count and attempts < count * 4:
            attempts += 1
            content = generate_random_content()
            img = create_recognition_sample(
                content,
                output_size=(img_width, img_height),
                augment=(split == "train"),
            )
            if img is None:
                continue

            filename = f"rec_{split}_{generated:06d}.png"
            filepath = os.path.join(img_dir, filename)
            cv2.imwrite(filepath, img)
            label_lines.append(f"{filename}\t{content}")
            generated += 1

            if generated % 500 == 0:
                print(f"  [{split}] {generated}/{count}")

        label_path = os.path.join(output_dir, f"labels_{split}.txt")
        with open(label_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(label_lines))

        print(f"  [{split}] Done: {generated} images → {label_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic DataMatrix recognition dataset for CRNN training"
    )
    parser.add_argument("--num-images", type=int, default=5000,
                        help="Total images to generate (default: 5000)")
    parser.add_argument("--output-dir", type=str, default="training/data/recognition",
                        help="Output directory (default: training/data/recognition)")
    parser.add_argument("--img-width", type=int, default=256,
                        help="Image width (must match CRNN IMG_W, default: 256)")
    parser.add_argument("--img-height", type=int, default=32,
                        help="Image height (must match CRNN IMG_H, default: 32)")
    parser.add_argument("--train-ratio", type=float, default=0.7,
                        help="Fraction for training split (default: 0.7)")
    args = parser.parse_args()

    print(f"Generating {args.num_images} recognition samples in '{args.output_dir}' …")
    generate_dataset(
        num_images=args.num_images,
        output_dir=args.output_dir,
        img_width=args.img_width,
        img_height=args.img_height,
        train_ratio=args.train_ratio,
    )
    print("Recognition dataset generation complete.")


if __name__ == "__main__":
    main()
