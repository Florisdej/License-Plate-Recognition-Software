# ALPR System — Raspberry Pi 4 Setup & Usage Guide

This guide walks you through installing and running the license plate recognition system on a Raspberry Pi 4, including the web dashboard and optional Pi Camera Module support.

---

## Requirements

| Component | Minimum |
|---|---|
| Hardware | Raspberry Pi 4 (2 GB RAM or more) |
| OS | Raspberry Pi OS Bookworm or Bullseye (64-bit recommended) |
| Camera | USB webcam **or** Pi Camera Module v2/v3 |
| Storage | 8 GB free on SD card |
| Network | Required for initial install; optional after |

---

## Step 1 — Copy the files to your Pi

From your development machine, copy the `alpr_rpi4/` folder to the Pi:

```bash
scp -r alpr_rpi4/ pi@<your-pi-ip>:~/alpr_rpi4
```

Or clone only the `alpr_rpi4/` folder (faster — skips the rest of the repo):

```bash
git clone --filter=blob:none --sparse https://github.com/Florisdej/License-Plate-Recognition-Software.git
cd License-Plate-Recognition-Software
git sparse-checkout set alpr_rpi4
git checkout v2
cd alpr_rpi4
```

---

## Step 2 — Run the setup script

```bash
cd ~/alpr_rpi4
bash setup_rpi4.sh
```

The script will:
1. Install system packages (`python3`, `libopencv`, etc.)
2. Create a Python virtual environment at `~/alpr_env`
3. Install CPU-only PyTorch
4. Install all Python dependencies
5. Create `model/` and `output/` directories
6. Optionally install a systemd service (runs ALPR on boot)

---

## Step 3 — Add your model

Copy your trained YOLOv8 model file to the Pi:

```bash
scp model/best.pt pi@<your-pi-ip>:~/alpr_rpi4/model/best.pt
```

### Export to ONNX (strongly recommended — 3–5x faster)

Activate the virtual environment and export:

```bash
source ~/alpr_env/bin/activate
python export_onnx.py --model model/best.pt
```

This creates `model/best.onnx`. The system will use it automatically if `USE_ONNX = True` in `config.py` (the default).

---

## Step 4 — Test with a single image

```bash
source ~/alpr_env/bin/activate
python main.py --image test.jpg
```

Cropped plates are saved to `output/`.

---

## Step 5 — Run with a USB webcam

**Headless (no display):**

```bash
python main.py --camera 0 --no-display
```

**With web dashboard** — open `http://<your-pi-ip>:5000` in a browser on any device on the same network:

```bash
python main.py --camera 0 --web
```

---

## Step 6 — Run with Pi Camera Module (optional)

The Pi Camera Module works via **picamera2 + libcamera** — no legacy camera stack needed.
The setup script installs the required system packages automatically on aarch64.

> **Bookworm note:** the old `raspi-config → Interface Options → Camera` toggle no longer exists and is not required. libcamera auto-detects the camera.

Run:

```bash
python main.py --picamera2 --web
```

If you see `No module named 'libcamera'`, the system packages were not installed.
Fix it with:

```bash
sudo apt-get install -y python3-picamera2 python3-libcamera python3-kms++
```

---

## Step 7 — Run as a systemd service (auto-start on boot)

If you chose to install the service during `setup_rpi4.sh`, use these commands:

```bash
# Start the service now
sudo systemctl start alpr

# Check status
sudo systemctl status alpr

# Follow live logs
sudo journalctl -u alpr -f

# Stop the service
sudo systemctl stop alpr

# Disable auto-start on boot
sudo systemctl disable alpr
```

The service runs `python main.py --camera 0 --web --service` by default.
Edit `/etc/systemd/system/alpr.service` to change the camera source or port, then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart alpr
```

---

## Web Dashboard

When `--web` is used, a dashboard is available at **`http://<your-pi-ip>:5000`**.

| Page / Endpoint | Description |
|---|---|
| `GET /` | Dashboard: live stream, last 10 plates, FPS, uptime |
| `GET /stream` | Raw MJPEG stream (embed in other apps) |
| `GET /api/status` | JSON: last plate, FPS, uptime, total detections |
| `GET /api/history` | JSON array of last 100 detections |
| `POST /api/clear` | Clear detection history |

> **Tip:** Find your Pi's IP address with `hostname -I`.

---

## Configuration

All settings are in `config.py`. Key RPi4 options:

| Setting | Default | Description |
|---|---|---|
| `DETECTION_IMG_SIZE` | `320` | Model input size — lower = faster |
| `VIDEO_FRAME_SKIP` | `5` | Process every Nth frame |
| `VIDEO_DISPLAY` | `False` | Show OpenCV window (needs display) |
| `USE_ONNX` | `True` | Use ONNX runtime if `.onnx` exists |
| `USE_PICAMERA2` | `False` | Use Pi Camera Module |
| `WEB_UI_PORT` | `5000` | Web dashboard port |
| `SAVE_ANNOTATED` | `False` | Save annotated frames to disk |
| `OCR_CACHE_SIZE` | `64` | LRU cache for OCR results |
| `REQUIRE_NL_PATTERN` | `True` | Only accept valid Dutch plate formats |

---

## Troubleshooting

**`No module named 'picamera2'` or `No module named 'libcamera'`**
The picamera2/libcamera Python bindings must come from the system repo, not pip.
Install with:
```bash
sudo apt-get install -y python3-picamera2 python3-libcamera python3-kms++
```
Then re-create the virtual environment so it picks up the system packages:
```bash
rm -rf ~/alpr_env
bash setup_rpi4.sh
```

**`Cannot open camera 0`**
Check the webcam is connected: `ls /dev/video*`. Try index `1` or `2` if multiple cameras are present.

**ONNX model not found / PyTorch fallback**
Run `export_onnx.py` (Step 3) and confirm `model/best.onnx` exists. Set `USE_ONNX = True` in `config.py`.

**Web dashboard unreachable**
Confirm the Pi's firewall allows port 5000:
```bash
sudo ufw allow 5000
```

**Low FPS**
- Increase `VIDEO_FRAME_SKIP` (e.g. `7` or `10`)
- Lower `DETECTION_IMG_SIZE` to `224`
- Ensure you are using the ONNX model, not PyTorch

---

## Folder Structure

```
alpr_rpi4/
├── config.py               # All settings
├── detector.py             # ONNX + PyTorch detection
├── preprocessor.py         # Image preprocessing
├── ocr_engine.py           # EasyOCR wrapper
├── color_filter.py         # Blue/yellow plate filter
├── pipeline.py             # Full detection pipeline
├── translations.py         # NL/EN strings
├── main.py                 # CLI entry point
├── web_ui.py               # Flask web dashboard
├── export_onnx.py          # .pt → .onnx exporter
├── requirements_rpi4.txt   # Python dependencies
├── setup_rpi4.sh           # Install script
├── alpr.service            # Systemd unit file
├── model/                  # Place best.pt / best.onnx here
└── output/                 # Detection results saved here
```
