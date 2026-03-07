#!/usr/bin/env python3
"""
Standalone camera diagnostic script for Raspberry Pi.

Run on the Pi (no venv required, uses system Python):
    python3 scripts/diagnose_camera.py

Or inside the venv:
    .venv/bin/python scripts/diagnose_camera.py
"""
from __future__ import annotations

import subprocess
import sys

SEP = "-" * 60


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def info(msg: str) -> None:
    print(f"         {msg}")


# ---------------------------------------------------------------------------
# 1. Python environment
# ---------------------------------------------------------------------------
section("1. Python environment")
ok(f"Python {sys.version}")
ok(f"Executable: {sys.executable}")

# ---------------------------------------------------------------------------
# 2. System: libcamera-hello
# ---------------------------------------------------------------------------
section("2. libcamera-hello --list-cameras")
try:
    r = subprocess.run(
        ["libcamera-hello", "--list-cameras"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    combined = r.stdout + r.stderr
    if r.returncode == 0 or combined.strip():
        for line in combined.splitlines():
            info(line)
        if "No cameras available" in combined or ("0" not in combined):
            warn("libcamera-hello did not report any cameras \u2014 check cable / overlay")
        else:
            ok("libcamera sees at least one camera")
    else:
        fail(f"libcamera-hello returned code {r.returncode} with no output")
except FileNotFoundError:
    fail("libcamera-hello not found \u2014 run: sudo apt install libcamera-apps")
except Exception as exc:
    fail(f"Unexpected error: {exc}")

# ---------------------------------------------------------------------------
# 3. System: v4l2-ctl
# ---------------------------------------------------------------------------
section("3. v4l2-ctl --list-devices")
try:
    r = subprocess.run(
        ["v4l2-ctl", "--list-devices"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    output = r.stdout or r.stderr
    if output.strip():
        for line in output.splitlines():
            info(line)
    else:
        warn("No v4l2 devices found")
except FileNotFoundError:
    warn("v4l2-ctl not found \u2014 run: sudo apt install v4l-utils")
except Exception as exc:
    fail(f"Unexpected error: {exc}")

# ---------------------------------------------------------------------------
# 4. picamera2 importability
# ---------------------------------------------------------------------------
section("4. picamera2 Python package")
picam2_ok = False
try:
    import picamera2  # type: ignore

    ok(f"picamera2 version : {getattr(picamera2, '__version__', 'unknown')}")
    ok(f"picamera2 path    : {picamera2.__file__}")
    picam2_ok = True
except ImportError as exc:
    fail(f"Cannot import picamera2: {exc}")
    warn("If picamera2 is installed via apt (not pip), your venv needs")
    warn("  --system-site-packages to see it.  Fix:")
    warn("  rm -rf .venv")
    warn("  python3 -m venv --system-site-packages .venv")
    warn("  source .venv/bin/activate && pip install -r requirements.txt")

# ---------------------------------------------------------------------------
# 5. libcamera Python bindings
# ---------------------------------------------------------------------------
section("5. libcamera Python bindings")
try:
    import libcamera  # type: ignore

    ok(f"libcamera version : {getattr(libcamera, '__version__', 'unknown')}")
except ImportError as exc:
    warn(f"libcamera Python bindings not found: {exc}")
    warn("Autofocus will be disabled, but cameras should still work.")
    warn("Fix: sudo apt install python3-libcamera  (then use system-site-packages venv)")

# ---------------------------------------------------------------------------
# 6. global_camera_info()
# ---------------------------------------------------------------------------
section("6. Picamera2.global_camera_info()")
if picam2_ok:
    try:
        from picamera2 import Picamera2  # type: ignore

        cams = Picamera2.global_camera_info()
        if cams:
            ok(f"Found {len(cams)} camera(s):")
            for c in cams:
                info(str(c))
        else:
            fail("global_camera_info() returned empty list")
            warn("Camera module may not be connected or detected by the kernel.")
            warn("Check: sudo dmesg | grep -i imx  (or vcm / ov)")
    except Exception as exc:
        fail(f"global_camera_info() raised: {exc}")
else:
    warn("Skipped (picamera2 not importable)")

# ---------------------------------------------------------------------------
# 7. Try opening each camera index
# ---------------------------------------------------------------------------
section("7. Try opening cameras (0 and 1)")
if picam2_ok:
    for cam_num in (0, 1):
        print(f"\n  --- Camera {cam_num} ---")
        try:
            from picamera2 import Picamera2  # type: ignore

            picam = Picamera2(camera_num=cam_num)
            opened = False
            for fmt in ["BGR888", "XBGR8888", "RGB888"]:
                try:
                    cfg = picam.create_video_configuration(
                        main={"size": (640, 480), "format": fmt}
                    )
                    picam.configure(cfg)
                    ok(f"Camera {cam_num}: configured with format {fmt}")
                    opened = True
                    break
                except Exception as fe:
                    warn(f"Camera {cam_num}: format {fmt} rejected \u2014 {fe}")

            if opened:
                picam.start()
                arr = picam.capture_array()
                ok(f"Camera {cam_num}: captured frame shape={arr.shape} dtype={arr.dtype}")
                picam.stop()
            picam.close()
        except Exception as exc:
            fail(f"Camera {cam_num}: {exc}")
else:
    warn("Skipped (picamera2 not importable)")

# ---------------------------------------------------------------------------
# 8. config/default.yaml camera section
# ---------------------------------------------------------------------------
section("8. Project config cameras section")
import os  # noqa: E402

config_path = os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")
try:
    import yaml  # type: ignore

    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    cameras_cfg = cfg.get("cameras", {})
    if cameras_cfg:
        for role, c in cameras_cfg.items():
            info(f"{role}: type={c.get('type')}, camera_num={c.get('camera_num')}")
    else:
        warn("No 'cameras' section found in config/default.yaml")
except ImportError:
    warn("PyYAML not installed in this Python \u2014 install it or run inside the venv")
except FileNotFoundError:
    warn(f"Config file not found: {config_path}")
except Exception as exc:
    fail(str(exc))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section("Summary / next steps")
print("""
  If step 2 (libcamera-hello) shows no cameras:
    \u2192 Physical issue: check ribbon cable, camera enable in /boot/config.txt
       sudo raspi-config  \u2192 Interface Options \u2192 Camera (legacy) or
       add  dtoverlay=vc4-kms-v3d  &  camera_auto_detect=1  to /boot/config.txt

  If step 4 (picamera2 import) failed:
    \u2192 Run: sudo apt install python3-picamera2 python3-libcamera
    \u2192 Recreate venv: python3 -m venv --system-site-packages .venv

  If step 6/7 show only 1 camera but config expects 2:
    \u2192 Only one CSI camera is connected; set local.camera_num to the same
       camera as global (0), or connect the second camera.

  If everything above is OK but the API still shows unavailable:
    \u2192 Hit GET http://localhost:8000/api/cameras/debug for runtime context.
""")
