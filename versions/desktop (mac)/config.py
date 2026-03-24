"""
ALPR Systeem - Configuratie
===========================
Centrale configuratie voor alle modules.
Pas deze waarden aan voor jouw specifieke setup.
"""

import logging
from pathlib import Path

# === Paden ===
BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "model" / "best.pt"
OUTPUT_DIR = BASE_DIR / "output"

# === Detectie (YOLOv8) ===
DETECTION_CONFIDENCE = 0.5      # Minimale confidence score voor detectie
DETECTION_IOU = 0.45            # IoU-drempel voor NMS (Non-Max Suppression)
DETECTION_IMG_SIZE = 640        # Input resolutie voor het model
DETECTION_MAX_DETECTIONS = 10   # Maximaal aantal detecties per frame

# === Preprocessing ===
# Doelgrootte voor gecropte kentekens (breedte, hoogte)
PLATE_TARGET_WIDTH = 300
PLATE_TARGET_HEIGHT = 80

# Preprocessing stappen (True = ingeschakeld)
PREPROCESSING = {
    "resize": True,             # Schaal naar doelgrootte
    "grayscale": True,          # Converteer naar grijswaarden
    "denoise": True,            # Ruisreductie (fastNlMeansDenoising)
    "contrast": True,           # CLAHE contrastverhoging
    "sharpen": True,            # Verscherping
    "binarize": True,           # Adaptieve binarisatie
}

# CLAHE parameters
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = (8, 8)

# Denoise kracht (hogere waarde = meer smoothing, maar verlies van detail)
DENOISE_STRENGTH = 10

# Binarisatie
BINARIZE_BLOCK_SIZE = 19       # Blokgrootte (oneven getal)
BINARIZE_C = 9                  # Constante afgetrokken van gemiddelde

# === OCR (EasyOCR) ===
OCR_LANGUAGES = ["en"]          # Talen voor OCR ('en' werkt goed voor EU-kentekens)
OCR_GPU = False                 # GPU gebruiken (False voor Raspberry Pi)
OCR_CONFIDENCE_MIN = 0.2        # Minimale OCR confidence om resultaat te accepteren
REQUIRE_NL_PATTERN = True       # Verwerp resultaten die niet op een geldig NL-kentekenpatroon lijken
OCR_TEXT_THRESHOLD = 0.3        # EasyOCR tekst-drempel (lager = meer recall bij wazig beeld)

# Scherptedrempel voor live camera (Laplacian-variantie); 0 = uitgeschakeld
SHARPNESS_MIN_VARIANCE = 80.0

# Toegestane tekens voor kentekens (letters + cijfers + streepje)
PLATE_CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"

# === Kleurfilter ===
COLOR_FILTER_ENABLED = False    # True = filter op kleur, False = toon alles (kleurlabel blijft zichtbaar)
PLATE_MODE = "all"              # "blue", "yellow", of "all"
VEHICLE_MODE = "car"           # "car", "scooter", "both"
COLOR_THRESHOLD = 0.3           # Min. percentage pixels om kleur toe te wijzen (0.0–1.0)

# === Video ===
VIDEO_FRAME_SKIP = 3            # Verwerk elke N-de frame (hoger = sneller, minder nauwkeurig)
VIDEO_DISPLAY = True            # Toon live preview (False voor headless/SSH)
VIDEO_MAX_FPS = 10              # Maximale verwerkingssnelheid

# === Output ===
SAVE_CROPPED_PLATES = True      # Sla gecropte kentekenafbeeldingen op
SAVE_ANNOTATED = True           # Sla geannoteerde frames op (met bounding boxes)
VERBOSE = True                  # Extra logging output

# === Ontwikkelaarsmodus ===
DEV_MODE = False                # Toon uitgebreide logging in GUI dev console

# === Logging ===
LOG_LEVEL = logging.INFO        # Minimaal logniveau (DEBUG, INFO, WARNING, ERROR)


def setup_logging():
    """Configureer centrale logging voor het hele systeem."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format="[%(levelname)s] %(name)s: %(message)s",
    )


def validate():
    """
    Valideer alle configuratiewaarden bij opstarten.

    Gooit ValueError als er ongeldige waarden zijn.
    Geeft waarschuwingen voor ontbrekende bestanden.
    """
    errors = []

    # Float thresholds moeten 0.0–1.0 zijn
    for name, value in [
        ("DETECTION_CONFIDENCE", DETECTION_CONFIDENCE),
        ("DETECTION_IOU", DETECTION_IOU),
        ("COLOR_THRESHOLD", COLOR_THRESHOLD),
        ("OCR_CONFIDENCE_MIN", OCR_CONFIDENCE_MIN),
    ]:
        if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
            errors.append(f"{name}={value} moet tussen 0.0 en 1.0 liggen")

    # Afmetingen moeten positief zijn
    if PLATE_TARGET_WIDTH <= 0:
        errors.append(f"PLATE_TARGET_WIDTH={PLATE_TARGET_WIDTH} moet > 0 zijn")
    if PLATE_TARGET_HEIGHT <= 0:
        errors.append(f"PLATE_TARGET_HEIGHT={PLATE_TARGET_HEIGHT} moet > 0 zijn")

    # BINARIZE_BLOCK_SIZE moet oneven en >= 3 zijn
    if BINARIZE_BLOCK_SIZE < 3:
        errors.append(f"BINARIZE_BLOCK_SIZE={BINARIZE_BLOCK_SIZE} moet >= 3 zijn")
    if BINARIZE_BLOCK_SIZE % 2 == 0:
        errors.append(f"BINARIZE_BLOCK_SIZE={BINARIZE_BLOCK_SIZE} moet een oneven getal zijn")

    # VIDEO_FRAME_SKIP >= 1
    if VIDEO_FRAME_SKIP < 1:
        errors.append(f"VIDEO_FRAME_SKIP={VIDEO_FRAME_SKIP} moet >= 1 zijn")

    # Model pad (waarschuwing, geen fout — detector gooit de exception)
    if not MODEL_PATH.exists():
        logging.getLogger(__name__).warning(
            "MODEL_PATH '%s' bestaat niet", MODEL_PATH
        )

    if errors:
        for e in errors:
            logging.getLogger(__name__).error("Ongeldige configuratie: %s", e)
        raise ValueError(
            f"Ongeldige configuratie: {len(errors)} fout(en) gevonden. "
            "Controleer config.py."
        )
