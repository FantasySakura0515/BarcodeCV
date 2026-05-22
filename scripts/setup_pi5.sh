#!/bin/bash
# Full setup script for BarcodeCV on Raspberry Pi 5
set -e

echo "=== BarcodeCV Raspberry Pi 5 Setup ==="

# System dependencies
bash scripts/install_dependencies.sh

# Python environment (with --system-site-packages so picamera2/libcamera
# installed by apt are accessible inside the venv)
echo "=== Setting up Python virtual environment ==="
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify cameras
echo ""
echo "=== Detecting cameras ==="
if command -v rpicam-hello >/dev/null 2>&1; then
    rpicam-hello --list-cameras 2>/dev/null || echo "No CSI cameras detected via rpicam"
elif command -v libcamera-hello >/dev/null 2>&1; then
    libcamera-hello --list-cameras 2>/dev/null || echo "No CSI cameras detected via libcamera"
else
    echo "No rpicam-hello/libcamera-hello command found"
fi
v4l2-ctl --list-devices 2>/dev/null || echo "No USB cameras detected via v4l2"

# Create data directories
mkdir -p data output/images logs models

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Activate venv:  source .venv/bin/activate"
echo "  2. Start backend:  python -m backend.api"
echo "  3. Camera debug:   curl http://localhost:8000/api/cameras/debug | python3 -m json.tool"
echo "  4. Camera list:    curl http://localhost:8000/api/cameras"
