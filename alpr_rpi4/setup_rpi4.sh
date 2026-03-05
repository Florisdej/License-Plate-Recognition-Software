#!/usr/bin/env bash
# ALPR System — RPi4 Setup Script
# ==================================
# Installs all dependencies and optionally configures a systemd service.
#
# Usage:
#   bash setup_rpi4.sh
#
# Tested on: Raspberry Pi OS (Bookworm / Bullseye), aarch64

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/alpr_env"

echo "================================================"
echo "  ALPR System — RPi4 Setup"
echo "================================================"
echo ""

# ------------------------------------------------------------------
# 1. System packages
# ------------------------------------------------------------------
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    libopencv-dev \
    libatlas-base-dev \
    libjpeg-dev libpng-dev libtiff-dev \
    libhdf5-dev \
    libgl1 \
    libglib2.0-0 \
    git \
    -qq
echo "  System packages installed."

# ------------------------------------------------------------------
# 2. Virtual environment
# ------------------------------------------------------------------
echo "[2/6] Creating virtual environment at $VENV_DIR..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  Virtual environment created."
else
    echo "  Virtual environment already exists — skipping."
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

# ------------------------------------------------------------------
# 3. CPU-only PyTorch
# ------------------------------------------------------------------
echo "[3/6] Installing CPU-only PyTorch (this may take several minutes)..."
pip install torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu \
    -q
echo "  PyTorch installed."

# ------------------------------------------------------------------
# 4. Python packages
# ------------------------------------------------------------------
echo "[4/6] Installing Python packages from requirements_rpi4.txt..."
pip install -r "$SCRIPT_DIR/requirements_rpi4.txt" -q
echo "  Python packages installed."

# ------------------------------------------------------------------
# 5. Create directories
# ------------------------------------------------------------------
echo "[5/6] Creating model/ and output/ directories..."
mkdir -p "$SCRIPT_DIR/model"
mkdir -p "$SCRIPT_DIR/output"
echo "  Directories created."

echo ""
echo "================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Copy your model file to: $SCRIPT_DIR/model/best.pt"
echo "  2. Export to ONNX (faster inference):"
echo "     source $VENV_DIR/bin/activate"
echo "     python $SCRIPT_DIR/export_onnx.py --model $SCRIPT_DIR/model/best.pt"
echo "  3. Test a single image:"
echo "     python $SCRIPT_DIR/main.py --image test.jpg"
echo "  4. Start live detection + web dashboard:"
echo "     python $SCRIPT_DIR/main.py --camera 0 --web"
echo "================================================"
echo ""

# ------------------------------------------------------------------
# 6. Optional: systemd service
# ------------------------------------------------------------------
echo "[6/6] Install systemd service? (runs ALPR on boot)"
read -r -p "  Install service? [y/N] " REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    SERVICE_FILE="$SCRIPT_DIR/alpr.service"
    TARGET="/etc/systemd/system/alpr.service"

    # Patch WorkingDirectory and ExecStart to use actual paths
    sed \
        -e "s|/home/pi/alpr_rpi4|$SCRIPT_DIR|g" \
        -e "s|/home/pi/alpr_env|$VENV_DIR|g" \
        -e "s|User=pi|User=$(whoami)|g" \
        "$SERVICE_FILE" | sudo tee "$TARGET" > /dev/null

    sudo systemctl daemon-reload
    sudo systemctl enable alpr
    echo ""
    echo "  Service installed and enabled."
    echo ""
    echo "  Commands:"
    echo "    sudo systemctl start alpr    # start now"
    echo "    sudo systemctl status alpr   # check status"
    echo "    sudo journalctl -u alpr -f   # follow logs"
    echo "    sudo systemctl disable alpr  # remove from boot"
else
    echo "  Skipping service installation."
fi

echo ""
echo "  Done. Activate the environment with:"
echo "    source $VENV_DIR/bin/activate"
echo ""
