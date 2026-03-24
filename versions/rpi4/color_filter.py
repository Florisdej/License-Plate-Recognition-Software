"""
ALPR System — Color Filter Module
====================================
Classifies plates by color (blue/yellow) via HSV analysis
and filters detections based on the configured plate_mode.
"""

import logging
import cv2
import numpy as np
from typing import List, Tuple
import config

logger = logging.getLogger(__name__)

HSV_RANGES = {
    "BLUE": {
        "lower": np.array([90, 60, 40]),
        "upper": np.array([140, 255, 255]),
    },
    "YELLOW": {
        "lower": np.array([10, 70, 70]),
        "upper": np.array([45, 255, 255]),
    },
}


def classify_plate_color(cropped_image: np.ndarray, threshold: float = 0.3) -> str:
    """
    Classify the color of a cropped plate image.

    Args:
        cropped_image: Cropped plate region (BGR)
        threshold:     Minimum pixel percentage to assign a color (0.0–1.0)

    Returns:
        "BLUE", "YELLOW" or "UNKNOWN"
    """
    if cropped_image is None or cropped_image.size == 0:
        return "UNKNOWN"

    try:
        small_crop = cv2.resize(cropped_image, (64, 64), interpolation=cv2.INTER_LINEAR)
        hsv = cv2.cvtColor(small_crop, cv2.COLOR_BGR2HSV)
    except Exception as e:
        logger.warning("[ColorFilter] Color conversion failed (%s)", e)
        return "UNKNOWN"

    total_pixels = hsv.shape[0] * hsv.shape[1]
    if total_pixels == 0:
        return "UNKNOWN"

    scores = {}
    for color_name, ranges in HSV_RANGES.items():
        try:
            mask = cv2.inRange(hsv, ranges["lower"], ranges["upper"])
            scores[color_name] = cv2.countNonZero(mask) / total_pixels
        except Exception:
            scores[color_name] = 0.0

    if not scores:
        return "UNKNOWN"

    best_color = max(scores, key=scores.get)
    best_score = scores[best_color]

    if best_score >= threshold:
        if config.VERBOSE:
            pct = {k: f"{v:.1%}" for k, v in scores.items()}
            logger.debug("[ColorFilter] Color: %s (scores: %s)", best_color, pct)
        return best_color

    return "UNKNOWN"


def filter_by_color(detections: list, plate_colors: List[str]) -> Tuple[list, list]:
    """
    Filter detections based on the configured plate_mode.

    If COLOR_FILTER_ENABLED is False, all detections pass through
    (color labels are still available).
    """
    if not config.COLOR_FILTER_ENABLED:
        return detections, plate_colors

    mode = config.PLATE_MODE.lower()
    if mode == "all":
        return detections, plate_colors

    target = mode.upper()
    filtered_detections = []
    filtered_colors = []

    for det, color in zip(detections, plate_colors):
        if color == target:
            filtered_detections.append(det)
            filtered_colors.append(color)

    if config.VERBOSE:
        total = len(detections)
        kept = len(filtered_detections)
        logger.debug("[ColorFilter] Mode '%s': %d/%d detections kept", mode, kept, total)

    return filtered_detections, filtered_colors
