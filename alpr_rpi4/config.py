"""
ALPR System — Raspberry Pi 4 Configuration
============================================
RPi4-optimised defaults: headless, ONNX inference, smaller model input,
picamera2 support, Flask web UI.
"""

import logging
from pathlib import Path

# === Paths ===
BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "model" / "best.pt"
ONNX_MODEL_PATH = BASE_DIR / "model" / "best.onnx"
OUTPUT_DIR = BASE_DIR / "output"

# === Detection (YOLOv8 / ONNX) ===
DETECTION_CONFIDENCE = 0.5
DETECTION_IOU = 0.45
DETECTION_IMG_SIZE = 320        # Halved vs desktop (2x faster on ARM)
DETECTION_MAX_DETECTIONS = 10

# ONNX runtime (faster on RPi4 than PyTorch)
USE_ONNX = True                 # Use ONNX if .onnx file exists; PyTorch fallback

# === Preprocessing ===
PLATE_TARGET_WIDTH = 200        # Smaller than desktop (300) to save CPU
PLATE_TARGET_HEIGHT = 60

PREPROCESSING = {
    "resize": True,
    "grayscale": True,
    "denoise": True,
    "contrast": True,
    "sharpen": True,
    "binarize": True,
}

CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = (8, 8)
DENOISE_STRENGTH = 10
BINARIZE_BLOCK_SIZE = 19
BINARIZE_C = 9

# === OCR (EasyOCR) ===
OCR_LANGUAGES = ["en"]
OCR_GPU = False                 # No GPU on RPi4
OCR_CONFIDENCE_MIN = 0.2
REQUIRE_NL_PATTERN = True
OCR_TEXT_THRESHOLD = 0.3
OCR_CACHE_SIZE = 64             # Smaller cache to save RAM (desktop: 128)

SHARPNESS_MIN_VARIANCE = 80.0
PLATE_CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"

# === Color filter ===
COLOR_FILTER_ENABLED = False
PLATE_MODE = "all"
VEHICLE_MODE = "car"
COLOR_THRESHOLD = 0.3

# === Video / Camera ===
VIDEO_FRAME_SKIP = 5            # Higher than desktop (3) to reduce CPU load
VIDEO_DISPLAY = False           # Headless default (no X display on RPi)
VIDEO_MAX_FPS = 5

USE_PICAMERA2 = False           # Set True to use Pi Camera Module via picamera2

# === Web UI (Flask) ===
WEB_UI_HOST = "0.0.0.0"
WEB_UI_PORT = 5000

# === Output ===
SAVE_CROPPED_PLATES = True
SAVE_ANNOTATED = False          # Disable by default to reduce SD card writes
VERBOSE = True

# === Developer mode ===
DEV_MODE = False

# === Logging ===
LOG_LEVEL = logging.INFO


def setup_logging():
    """Configure central logging."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format="[%(levelname)s] %(name)s: %(message)s",
    )


def validate():
    """
    Validate all config values at startup.
    Raises ValueError for invalid values.
    """
    errors = []

    for name, value in [
        ("DETECTION_CONFIDENCE", DETECTION_CONFIDENCE),
        ("DETECTION_IOU", DETECTION_IOU),
        ("COLOR_THRESHOLD", COLOR_THRESHOLD),
        ("OCR_CONFIDENCE_MIN", OCR_CONFIDENCE_MIN),
    ]:
        if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
            errors.append(f"{name}={value} must be between 0.0 and 1.0")

    if PLATE_TARGET_WIDTH <= 0:
        errors.append(f"PLATE_TARGET_WIDTH={PLATE_TARGET_WIDTH} must be > 0")
    if PLATE_TARGET_HEIGHT <= 0:
        errors.append(f"PLATE_TARGET_HEIGHT={PLATE_TARGET_HEIGHT} must be > 0")

    if BINARIZE_BLOCK_SIZE < 3:
        errors.append(f"BINARIZE_BLOCK_SIZE={BINARIZE_BLOCK_SIZE} must be >= 3")
    if BINARIZE_BLOCK_SIZE % 2 == 0:
        errors.append(f"BINARIZE_BLOCK_SIZE={BINARIZE_BLOCK_SIZE} must be odd")

    if VIDEO_FRAME_SKIP < 1:
        errors.append(f"VIDEO_FRAME_SKIP={VIDEO_FRAME_SKIP} must be >= 1")

    if not MODEL_PATH.exists() and not ONNX_MODEL_PATH.exists():
        logging.getLogger(__name__).warning(
            "Neither MODEL_PATH '%s' nor ONNX_MODEL_PATH '%s' exists",
            MODEL_PATH, ONNX_MODEL_PATH,
        )

    if errors:
        for e in errors:
            logging.getLogger(__name__).error("Invalid config: %s", e)
        raise ValueError(
            f"Invalid configuration: {len(errors)} error(s). Check config.py."
        )
