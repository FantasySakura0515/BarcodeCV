# YOLO Training (Optional)

**You likely DON'T need this.** The main pipeline uses `pylibdmtx` and `zxing-cpp`
to directly detect and decode DataMatrix codes from full images — no custom ML model needed.

## When you MIGHT need YOLO training

- DataMatrix codes are very small (< 5mm) and far from the camera
- Library-based scanning misses codes that you can see visually
- You need faster detection with many (50+) codes per image
- You need to detect DataMatrix *locations* without decoding (counting only)

## Training workflow

```bash
# 1. Generate synthetic training data
python -m training.prepare_dataset --num-images 2000

# 2. Train (run on a machine with GPU, NOT on Raspberry Pi)
python -m training.train --data training/data/data.yaml --epochs 150

# 3. Evaluate
python -m training.evaluate --model runs/detect/datamatrix_v1/weights/best.pt

# 4. Export for Pi 5
python -m training.export_model --model runs/detect/datamatrix_v1/weights/best.pt --format ncnn
```

## Required packages (training machine only)

```bash
pip install ultralytics pylibdmtx albumentations
```
