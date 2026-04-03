#!/bin/bash
# Install system-level dependencies for BarcodeCV on Raspberry Pi OS
set -e

echo "=== Installing system dependencies ==="
sudo apt update
sudo apt install -y \
    libdmtx-dev \
    libdmtx0t64 \
    python3-picamera2 \
    python3-libcamera \
    v4l-utils

if apt-cache show rpicam-apps >/dev/null 2>&1; then
    sudo apt install -y rpicam-apps
else
    sudo apt install -y libcamera-apps
fi

echo "=== System dependencies installed ==="
