"""Evaluate trained YOLO model on test set.

Usage:
    python -m training.evaluate --model runs/detect/datamatrix_v1/weights/best.pt
"""

import argparse

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Evaluate YOLO DataMatrix model")
    parser.add_argument("--model", type=str, required=True,
                        help="Path to trained model weights")
    parser.add_argument("--data", type=str, default="training/data/data.yaml")
    parser.add_argument("--split", type=str, default="test",
                        choices=["val", "test"])
    args = parser.parse_args()

    model = YOLO(args.model)
    metrics = model.val(data=args.data, split=args.split)

    print(f"\n=== Evaluation Results ({args.split} set) ===")
    print(f"  mAP50:    {metrics.box.map50:.4f}")
    print(f"  mAP50-95: {metrics.box.map:.4f}")
    print(f"  Precision: {metrics.box.mp:.4f}")
    print(f"  Recall:    {metrics.box.mr:.4f}")


if __name__ == "__main__":
    main()
