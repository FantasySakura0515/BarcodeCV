#!/bin/bash
# Fix "no module named 'picamera2'" on Raspberry Pi.
#
# Root cause: the .venv was created WITHOUT --system-site-packages, so
# picamera2 / libcamera (installed via apt) are invisible to the venv.
#
# Usage (run from the repo root):
#   bash scripts/fix_venv_pi.sh

set -e
cd "$(dirname "$0")/.."

echo "=== BarcodeCV: fix picamera2 in venv ==="
echo ""

# 1. Verify system picamera2 is present
if ! python3 -c "import picamera2" 2>/dev/null; then
    echo "[STEP 1] picamera2 not found in system Python — installing via apt..."
    sudo apt update
    sudo apt install -y python3-picamera2 python3-libcamera
else
    echo "[STEP 1] System Python has picamera2 — OK"
fi

# 2. Check if existing .venv already works
if [ -d ".venv" ]; then
    if .venv/bin/python -c "import picamera2" 2>/dev/null; then
        echo "[STEP 2] .venv already has picamera2 — nothing to do!"
        exit 0
    fi
    echo "[STEP 2] .venv cannot import picamera2 — recreating with --system-site-packages..."
    rm -rf .venv
else
    echo "[STEP 2] No .venv found — will create one."
fi

# 3. Recreate venv with system-site-packages
echo "[STEP 3] Creating .venv with --system-site-packages..."
python3 -m venv --system-site-packages .venv

# 4. Reinstall project dependencies
echo "[STEP 4] Installing project dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 5. Verify
echo ""
echo "[STEP 5] Verifying..."
if .venv/bin/python -c "import picamera2; print('picamera2 OK:', picamera2.__version__)"; then
    echo ""
    echo "=== Done! picamera2 is now available in .venv ==="
    echo ""
    echo "Next:"
    echo "  source .venv/bin/activate"
    echo "  python -m backend.api"
    echo "  # Then: curl http://localhost:8000/api/cameras/debug | python3 -m json.tool"
else
    echo ""
    echo "[ERROR] picamera2 still not importable. Please check:"
    echo "  1. sudo apt install python3-picamera2"
    echo "  2. python3 -c 'import picamera2'  # must work outside venv first"
fi
