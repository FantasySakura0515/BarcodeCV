"""Train YOLO model for DataMatrix detection.

Usage:
    python -m training.train --data training/data/data.yaml --epochs 150
"""

import argparse

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Train YOLO for DataMatrix detection")
    parser.add_argument("--model", type=str, default="yolo11n.pt",
                        help="Pre-trained model to start from")
    parser.add_argument("--data", type=str, default="training/data/data.yaml",
                        help="Path to data.yaml")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="0",
                        help="Device: '0' for GPU, 'cpu' for CPU")
    parser.add_argument("--name", type=str, default="datamatrix_v1")
    args = parser.parse_args()

    model = YOLO(args.model)

    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=30,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=5,
        augment=True,
        mosaic=1.0,
        mixup=0.1,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=15.0,
        translate=0.1,
        scale=0.5,
        perspective=0.001,
        flipud=0.5,
        fliplr=0.5,
        device=args.device,
        project="runs/detect",
        name=args.name,
        save=True,
        save_period=10,
        plots=True,
    )

    print(f"\nTraining complete! Best model: runs/detect/{args.name}/weights/best.pt")


if __name__ == "__main__":
    main()
