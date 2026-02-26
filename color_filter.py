"""
ALPR Systeem - Kleurfiltermodule
=================================
Classificeert kentekens op kleur (blauw/geel) via HSV-analyse
en filtert detecties op basis van de ingestelde plate_mode.
"""

import logging
import cv2
import numpy as np
from typing import List, Tuple
import config

logger = logging.getLogger(__name__)


# HSV-ranges voor kentekenkleurdetectie
HSV_RANGES = {
    "BLUE": {
        "lower": np.array([90, 60, 40]),    # Ruimer voor donker/lichtblauw
        "upper": np.array([140, 255, 255]),
    },
    "YELLOW": {
        "lower": np.array([10, 70, 70]),    # Ruimer voor oranje-geel en lichtgeel
        "upper": np.array([45, 255, 255]),
    },
}


def classify_plate_color(cropped_image: np.ndarray, threshold: float = 0.3) -> str:
    """
    Classificeer de kleur van een gecropte kentekenafbeelding.

    Converteert naar HSV en berekent het percentage pixels dat binnen
    de blauw- en geel-ranges valt. Retourneert de kleur met het
    hoogste percentage, mits boven de drempelwaarde.

    Args:
        cropped_image: Gecropte kentekenregio (BGR)
        threshold:     Minimaal percentage pixels om een kleur toe te wijzen (0.0–1.0)

    Returns:
        "BLUE", "YELLOW" of "UNKNOWN"
    """
    if cropped_image is None or cropped_image.size == 0:
        return "UNKNOWN"

    # Optimalisatie: Resize naar klein formaat voor snellere HSV conversie
    try:
        small_crop = cv2.resize(cropped_image, (64, 64), interpolation=cv2.INTER_LINEAR)
        hsv = cv2.cvtColor(small_crop, cv2.COLOR_BGR2HSV)
    except Exception as e:
        logger.warning("[ColorFilter] Kleurconversie mislukt (%s)", e)
        return "UNKNOWN"

    total_pixels = hsv.shape[0] * hsv.shape[1]

    if total_pixels == 0:
        return "UNKNOWN"

    # Bereken percentage voor elke kleur
    scores = {}
    for color_name, ranges in HSV_RANGES.items():
        try:
            mask = cv2.inRange(hsv, ranges["lower"], ranges["upper"])
            pixel_count = cv2.countNonZero(mask)
            scores[color_name] = pixel_count / total_pixels
        except Exception:
            scores[color_name] = 0.0

    if not scores:
        return "UNKNOWN"

    # Bepaal de winnende kleur
    best_color = max(scores, key=scores.get)
    best_score = scores[best_color]

    if best_score >= threshold:
        if config.VERBOSE:
            pct = {k: f"{v:.1%}" for k, v in scores.items()}
            logger.debug("[ColorFilter] Kleur: %s (scores: %s)", best_color, pct)
        return best_color

    if config.VERBOSE:
        pct = {k: f"{v:.1%}" for k, v in scores.items()}
        logger.debug("[ColorFilter] Kleur: UNKNOWN (scores: %s, drempel: %.0%%)", pct, threshold)

    return "UNKNOWN"


def filter_by_color(detections: list, plate_colors: List[str]) -> Tuple[list, list]:
    """
    Filter detecties op basis van de ingestelde plate_mode.

    Als color_filter_enabled is uitgeschakeld, worden alle detecties
    doorgelaten (maar de kleurlabels blijven beschikbaar).

    Args:
        detections:   Lijst van detecties
        plate_colors: Lijst van kleurlabels (zelfde volgorde als detections)

    Returns:
        Tuple van (gefilterde_detecties, gefilterde_kleuren)
    """
    if not config.COLOR_FILTER_ENABLED:
        # Filter uit: alles doorlaten
        return detections, plate_colors

    mode = config.PLATE_MODE.lower()

    if mode == "all":
        return detections, plate_colors

    # Filter op basis van mode
    target = mode.upper()  # "BLUE" of "YELLOW"
    filtered_detections = []
    filtered_colors = []

    for det, color in zip(detections, plate_colors):
        if color == target:
            filtered_detections.append(det)
            filtered_colors.append(color)

    if config.VERBOSE:
        total = len(detections)
        kept = len(filtered_detections)
        logger.debug("[ColorFilter] Mode '%s': %d/%d detecties behouden", mode, kept, total)

    return filtered_detections, filtered_colors
