# BarcodeCV — Neural Network Training Plan

This directory contains everything needed to train and deploy a fully
neural-network-based DataMatrix scanning pipeline that **replaces
pylibdmtx and zxing-cpp** completely at inference time.

---

## Architecture Overview

```
Camera frame
     │
     ▼
┌─────────────────────────────────┐
│  Stage 1 — YOLO Detection       │   training/train.py
│  Locates DataMatrix regions     │   Finds bboxes, no library needed
└────────────────┬────────────────┘
                 │  cropped regions
                 ▼
┌─────────────────────────────────┐
│  Stage 2 — CRNN Recognition     │   training/train_recognizer.py
│  Reads encoded content string   │   CNN + BiLSTM + CTC decoder
└────────────────┬────────────────┘
                 │  list[ScanResult]
                 ▼
         Pipeline / API
```

| Component     | Architecture      | Library      | Training script              |
|---------------|-------------------|--------------|------------------------------|
| Detection     | YOLO11n           | ultralytics  | `training/train.py`          |
| Recognition   | CRNN (4×Conv + BiLSTM + CTC) | torch → ONNX | `training/train_recognizer.py` |
| Inference     | both models       | onnxruntime  | *(production, no training libs)* |

---

## Required Hardware

| Task            | Recommended                        |
|-----------------|------------------------------------|
| Training        | GPU machine (NVIDIA, CUDA ≥ 11.8)  |
| Inference (Pi5) | Raspberry Pi 5 (CPU only)          |
| Dataset size    | ≥ 2 000 detection + 5 000 recognition images |

---

## Step-by-step Training Workflow

### Prerequisites (training machine only)

```bash
pip install torch torchvision ultralytics pylibdmtx albumentations onnx onnxruntime
```

> **Note:** `pylibdmtx` here is used only as a *synthetic-image encoder* to
> generate DataMatrix bitmaps for training data.  It is **never** imported
> during inference.  The production `requirements.txt` does not include it.

---

### Stage 1 — DataMatrix Detection (YOLO)

The YOLO model locates DataMatrix code *positions* in a camera frame.

#### 1a. Generate synthetic detection dataset

```bash
python -m training.prepare_dataset \
    --num-images 3000 \
    --output-dir training/data \
    --img-size 640 \
    --max-codes 6
```

Output layout:
```
training/data/
├── images/{train,val,test}/
├── labels/{train,val,test}/
└── data.yaml
```

#### 1b. Train YOLO detection model

```bash
python -m training.train \
    --data training/data/data.yaml \
    --model yolo11n.pt \
    --epochs 150 \
    --imgsz 640 \
    --batch 16 \
    --device 0 \
    --name datamatrix_v1
```

Best weights: `runs/detect/datamatrix_v1/weights/best.pt`

#### 1c. Export YOLO for Pi 5 (NCNN format)

```bash
python -m training.export_model \
    --model runs/detect/datamatrix_v1/weights/best.pt \
    --format ncnn \
    --output-dir models
```

Update `config/default.yaml`:
```yaml
detection:
  model_path: "./models/datamatrix_v1_ncnn_model"
  model_format: "ncnn"
```

---

### Stage 2 — DataMatrix Recognition (CRNN)

The CRNN model reads the *encoded content* (e.g. `"PART-A0123"`) from a
cropped DataMatrix image.  It replaces pylibdmtx/zxing-cpp decoding entirely.

#### 2a. Generate recognition dataset

```bash
python -m training.prepare_recognition_dataset \
    --num-images 8000 \
    --output-dir training/data/recognition
```

Output layout:
```
training/data/recognition/
├── images/{train,val}/
├── labels_train.txt
└── labels_val.txt
```

Labels file format: `<filename>\t<content>` (one per line).

#### 2b. Train CRNN recogniser

```bash
python -m training.train_recognizer \
    --data training/data/recognition \
    --epochs 100 \
    --batch 64 \
    --device cuda \
    --name datamatrix_crnn_v1
```

Best checkpoint: `runs/recognize/datamatrix_crnn_v1/weights/best.pt`

Key hyper-parameters:

| Parameter      | Default | Notes                                 |
|----------------|---------|---------------------------------------|
| `--epochs`     | 100     | Increase to 150+ for real-world data  |
| `--batch`      | 64      | Reduce to 32 if GPU OOM               |
| `--hidden`     | 256     | BiLSTM hidden size                    |
| `--lr`         | 1e-3    | AdamW initial LR (cosine decay)       |
| `--patience`   | 15      | Early-stopping in val-check intervals |

#### 2c. Evaluate recogniser

```bash
python -m training.evaluate \
    --model runs/recognize/datamatrix_crnn_v1/weights/best.pt \
    --data training/data/recognition
```

Target metrics:
- Val exact-string accuracy > 90 % on synthetic data
- Val exact-string accuracy > 80 % on real captured data

#### 2d. Export CRNN to ONNX

```bash
python -m training.export_recognizer \
    --model runs/recognize/datamatrix_crnn_v1/weights/best.pt \
    --output models/datamatrix_crnn.onnx
```

---

### Final Configuration

Copy both exported models to the Pi 5 and update `config/default.yaml`:

```yaml
scanner:
  mode: "nn"           # neural network pipeline

detection:
  model_path: "./models/datamatrix_v1_ncnn_model"
  model_format: "ncnn"
  confidence_threshold: 0.5
  device: "cpu"

nn_decoding:
  crnn_model_path: "./models/datamatrix_crnn.onnx"
  pad_ratio: 0.05
```

Then start the system normally:

```bash
python -m backend.main --mode continuous
# or
python -m backend.api          # web UI
```

---

## Improving Recognition with Real Data

Synthetic data alone may not cover all real-world conditions (lighting,
angle, blur, partial occlusion).  To fine-tune on real images:

1. Run the system in `--mode continuous` for ≥ 30 minutes and collect
   frames saved to `./output/images/`.
2. Manually crop and label the DataMatrix regions: create a
   `labels_real.txt` with `<filename>\t<content>` entries.
3. Mix real data with synthetic during training:
   ```bash
   cat training/data/recognition/labels_train.txt labels_real.txt \
       > training/data/recognition/labels_train_mixed.txt
   ```
4. Retrain with the mixed dataset.

---

## File Reference

| File                                    | Purpose                                      |
|-----------------------------------------|----------------------------------------------|
| `training/train.py`                     | YOLO detection model training                |
| `training/prepare_dataset.py`           | Synthetic YOLO detection dataset generator   |
| `training/export_model.py`              | Export YOLO → NCNN / ONNX / TFLite           |
| `training/evaluate.py`                  | Evaluate YOLO model performance              |
| `training/train_recognizer.py`          | CRNN recognition model training              |
| `training/prepare_recognition_dataset.py` | Synthetic CRNN recognition dataset generator |
| `training/export_recognizer.py`         | Export CRNN PyTorch → ONNX                   |
| `training/models/crnn.py`               | CRNN model architecture (PyTorch)            |
| `backend/decoding/nn_decoder.py`        | Production inference (YOLO + CRNN, ONNX RT)  |
