#!/bin/bash
# ============================================================
#  ALPR Systeem - Raspberry Pi Setup Script
#  ============================================================
#  Dit script installeert alle benodigde dependencies op een
#  Raspberry Pi 4 (64-bit OS).
#
#  Gebruik: chmod +x setup_pi.sh && ./setup_pi.sh
# ============================================================

set -e  # Stop bij fouten

echo "============================================"
echo "  ALPR Systeem - Raspberry Pi Setup"
echo "============================================"

# Controleer of we op een Pi draaien
if [ -f /proc/device-tree/model ]; then
    echo "Hardware: $(cat /proc/device-tree/model)"
fi

echo ""
echo "[1/5] Systeem packages updaten..."
sudo apt update && sudo apt upgrade -y

echo ""
echo "[2/5] Systeemafhankelijkheden installeren..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    libopencv-dev \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libhdf5-dev \
    libhdf5-serial-dev \
    libharfbuzz0b \
    liblapack-dev \
    gfortran \
    libffi-dev \
    libssl-dev

echo ""
echo "[3/5] Python virtuele omgeving aanmaken..."
VENV_DIR="$HOME/alpr_env"

if [ -d "$VENV_DIR" ]; then
    echo "Virtuele omgeving bestaat al: $VENV_DIR"
else
    python3 -m venv "$VENV_DIR"
    echo "Virtuele omgeving aangemaakt: $VENV_DIR"
fi

# Activeer de virtuele omgeving
source "$VENV_DIR/bin/activate"

echo ""
echo "[4/5] Python packages installeren..."
pip install --upgrade pip setuptools wheel

# Installeer PyTorch voor ARM64 (CPU-versie)
echo "  → PyTorch installeren (dit kan even duren)..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Installeer project dependencies
echo "  → Project dependencies installeren..."
pip install -r requirements.txt

echo ""
echo "[5/5] Installatie verifiëren..."
python3 -c "
import cv2
import torch
import easyocr
from ultralytics import YOLO

print(f'  OpenCV:      {cv2.__version__}')
print(f'  PyTorch:     {torch.__version__}')
print(f'  Ultralytics: OK')
print(f'  EasyOCR:     OK')
print(f'  CUDA:        {\"Ja\" if torch.cuda.is_available() else \"Nee (CPU modus)\"}')
"

echo ""
echo "============================================"
echo "  Setup voltooid!"
echo "============================================"
echo ""
echo "Gebruik:"
echo "  source $VENV_DIR/bin/activate"
echo "  python main.py --image test.jpg"
echo ""
echo "Vergeet niet je model te plaatsen in:"
echo "  $(pwd)/model/best.pt"
echo ""
