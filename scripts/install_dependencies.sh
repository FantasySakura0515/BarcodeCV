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

echo "=== System dependencies installed ==="
