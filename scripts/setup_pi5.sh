#!/bin/bash
# Full setup script for BarcodeCV on Raspberry Pi 5
set -e

echo "=== BarcodeCV Raspberry Pi 5 Setup ==="

# System dependencies
bash scripts/install_dependencies.sh

# Python environment (with --system-site-packages for picamera2 access)
echo "=== Setting up Python virtual environment ==="
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify cameras
echo ""
echo "=== Detecting cameras ==="
libcamera-hello --list-cameras 2>/dev/null || echo "No CSI cameras detected via libcamera"
v4l2-ctl --list-devices 2>/dev/null || echo "No USB cameras detected via v4l2"

# Create data directories
mkdir -p data output/images logs models

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Activate venv: source venv/bin/activate"
echo "  2. Generate training data: python -m training.prepare_dataset"
echo "  3. Train model (on GPU machine): python -m training.train"
echo "  4. Export model: python -m training.export_model --model <path> --format ncnn"
echo "  5. Run scanner: python -m src.main --mode single"
echo "  6. Run calibration: python -m src.main --mode calibration"
