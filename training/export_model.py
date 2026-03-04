"""Export trained YOLO model for Raspberry Pi 5 deployment.

Usage:
    python -m training.export_model --model runs/detect/datamatrix_v1/weights/best.pt --format ncnn
"""

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Export YOLO model for deployment")
    parser.add_argument("--model", type=str, required=True,
                        help="Path to trained model weights (.pt)")
    parser.add_argument("--format", type=str, default="ncnn",
                        choices=["ncnn", "onnx", "tflite"],
                        help="Export format")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--output-dir", type=str, default="models",
                        help="Directory to copy exported model to")
    args = parser.parse_args()

    model = YOLO(args.model)

    print(f"Exporting model to {args.format} format...")
    export_path = model.export(format=args.format, imgsz=args.imgsz)
    print(f"Exported to: {export_path}")

    # Copy to models directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    export_path = Path(export_path)
    if export_path.is_dir():
        dest = output_dir / export_path.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(export_path, dest)
    else:
        shutil.copy2(export_path, output_dir / export_path.name)

    print(f"Copied to: {output_dir}")


if __name__ == "__main__":
    main()
