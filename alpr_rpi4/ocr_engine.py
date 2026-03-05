"""
ALPR System — OCR Module
==========================
EasyOCR integration for reading plate text from cropped images.
Includes Dutch/European plate post-processing.
LRU cache size is controlled via config.OCR_CACHE_SIZE (64 on RPi4).
"""

import collections
import logging
import re
import numpy as np
import cv2
from typing import Optional, Tuple
import easyocr
import config

logger = logging.getLogger(__name__)


class PlateOCR:
    """OCR engine for license plate recognition using EasyOCR."""

    CHAR_CORRECTIONS = {
        "O": "0", "I": "1", "S": "5", "B": "8", "G": "6", "Z": "2",
        "0": "O", "1": "I", "5": "S", "8": "B", "6": "G", "2": "Z",
    }

    NL_PLATE_PATTERNS = [
        (re.compile(r"^[A-Z]{2}-?\d{3}-?[A-Z]$"),      "XX-999-X (sidecode 9)"),
        (re.compile(r"^[A-Z]-?\d{3}-?[A-Z]{2}$"),       "X-999-XX (sidecode 8)"),
        (re.compile(r"^\d-?[A-Z]{3}-?\d{2}$"),          "9-XXX-99 (sidecode 7)"),
        (re.compile(r"^\d{2}-?[A-Z]{3}-?\d$"),          "99-XXX-9 (sidecode 6)"),
        (re.compile(r"^[A-Z]{3}-?\d{2}-?[A-Z]$"),       "XXX-99-X"),
        (re.compile(r"^[A-Z]-?\d{2}-?[A-Z]{3}$"),       "X-99-XXX"),
        (re.compile(r"^\d{2}-?[A-Z]{2}-?\d{2}$"),       "99-XX-99"),
        (re.compile(r"^[A-Z]{2}-?\d{2}-?[A-Z]{2}$"),    "XX-99-XX"),
        (re.compile(r"^\d{2}-?\d{2}-?[A-Z]{2}$"),       "99-99-XX"),
        (re.compile(r"^[A-Z]{2}-?\d{2}-?\d{2}$"),       "XX-99-99"),
        (re.compile(r"^\d{2}-?[A-Z]{2}-?[A-Z]{2}$"),    "99-XX-XX"),
        (re.compile(r"^[A-Z]{2}-?[A-Z]{2}-?\d{2}$"),    "XX-XX-99"),
    ]

    def __init__(self):
        logger.info("[OCR] Initialising EasyOCR (languages: %s)...", config.OCR_LANGUAGES)
        logger.info("[OCR] GPU: %s", config.OCR_GPU)

        try:
            self.reader = easyocr.Reader(
                config.OCR_LANGUAGES,
                gpu=config.OCR_GPU,
                verbose=False,
            )
        except Exception as e:
            raise RuntimeError(
                f"EasyOCR initialisation failed: {e}\n"
                "Check OCR_LANGUAGES and OCR_GPU in config.py."
            ) from e

        self._ocr_cache = collections.OrderedDict()
        logger.info("[OCR] EasyOCR ready")

    def _compute_phash(self, image: np.ndarray) -> int:
        """Average-hash of an image (64-bit int)."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_LINEAR)
        mean_val = resized.mean()
        phash = 0
        for pixel in resized.flatten():
            phash = (phash << 1) | (1 if pixel > mean_val else 0)
        return phash

    def clear_cache(self):
        self._ocr_cache.clear()
        logger.debug("[OCR] Cache cleared")

    def read_plate(self, plate_image: np.ndarray) -> Tuple[str, float]:
        """Read text from a single preprocessed plate image."""
        if plate_image is None or plate_image.size == 0:
            return "", 0.0

        results = self.reader.readtext(
            plate_image,
            detail=1,
            paragraph=False,
            min_size=10,
            text_threshold=config.OCR_TEXT_THRESHOLD,
            low_text=0.3,
            width_ths=0.7,
        )

        if not results:
            return "", 0.0

        candidates = []
        max_height = 0

        for (bbox, text, conf) in results:
            if conf < config.OCR_CONFIDENCE_MIN:
                continue
            h = abs(bbox[2][1] - bbox[1][1])
            if h > max_height:
                max_height = h
            center_x = (bbox[0][0] + bbox[1][0]) / 2
            candidates.append({"text": text, "conf": conf, "height": h,
                                "x": center_x, "bbox": bbox})

        if not candidates:
            return "", 0.0

        def sort_reading_order(items):
            if not items:
                return []
            items.sort(key=lambda i: i["bbox"][0][1])
            lines = []
            current_line = [items[0]]
            for item in items[1:]:
                prev = current_line[-1]
                y_diff = abs(item["bbox"][0][1] - prev["bbox"][0][1])
                h_avg = (item["height"] + prev["height"]) / 2
                if y_diff < (h_avg * 0.5):
                    current_line.append(item)
                else:
                    lines.append(current_line)
                    current_line = [item]
            lines.append(current_line)
            result = []
            for line in lines:
                line.sort(key=lambda i: i["x"])
                result.extend(line)
            return result

        candidates = sort_reading_order(candidates)

        thresh_factor = 0.5 if config.VEHICLE_MODE == "scooter" else 0.6
        min_height = max_height * thresh_factor

        final_pieces = []
        for item in candidates:
            text = item["text"].strip().upper()
            h = item["height"]
            if h < min_height:
                continue
            if len(text) < 3 and text.isalpha():
                continue
            if text in ["NL", "EU", "GARAGE", "DEALER", "AUTO", "BMW", "AUDI", "VOLVO"]:
                continue
            final_pieces.append(item)

        if not final_pieces:
            return "", 0.0

        combined_text = "".join([p["text"] for p in final_pieces])
        avg_conf = sum([p["conf"] for p in final_pieces]) / len(final_pieces)
        cleaned = self._clean_plate_text(combined_text)

        return cleaned, avg_conf

    def read_plate_multi(self, variants: list) -> Tuple[str, float]:
        """Try multiple preprocessing variants and return the best result."""
        if not variants:
            return "", 0.0

        phash = self._compute_phash(variants[0])
        if phash in self._ocr_cache:
            logger.debug("[OCR] Cache hit for phash %s", phash)
            self._ocr_cache.move_to_end(phash)
            return self._ocr_cache[phash]

        best_text = ""
        best_conf = 0.0

        for variant in variants:
            text, conf = self.read_plate(variant)

            if self.matches_nl_pattern(text):
                conf += 0.15  # Bonus for valid NL pattern

            if conf > best_conf and len(text) >= 4:
                best_text = text
                best_conf = conf

                # Early exit: high confidence + valid NL pattern
                if best_conf >= 0.7 and self.matches_nl_pattern(best_text):
                    break

        result = (best_text, min(best_conf, 1.0))

        self._ocr_cache[phash] = result
        self._ocr_cache.move_to_end(phash)
        if len(self._ocr_cache) > config.OCR_CACHE_SIZE:
            self._ocr_cache.popitem(last=False)

        return result

    def _clean_plate_text(self, raw_text: str) -> str:
        text = raw_text.upper().strip()
        text = re.sub(r"[^A-Z0-9\-\s]", "", text)
        stripped = re.sub(r"[\s\-]", "", text)
        formatted = self._format_nl_plate(stripped)
        return formatted if formatted else stripped

    def _format_nl_plate(self, text: str) -> Optional[str]:
        if len(text) < 5 or len(text) > 8:
            return None
        clean = text.replace("-", "")
        if len(clean) != 6:
            return None

        pattern = ""
        for char in clean:
            pattern += "D" if char.isdigit() else "L"

        format_map = {
            "LLDDDD": (2, 2, 2), "DDDDLL": (2, 2, 2), "DDLLDD": (2, 2, 2),
            "LLDDLL": (2, 2, 2), "LLLLDD": (2, 2, 2), "DDLLLL": (2, 2, 2),
            "DLLLDL": (1, 3, 2), "DLLLDD": (1, 3, 2), "DDLLLD": (2, 3, 1),
            "DDDLLL": (3, 3, 0), "LDDDLL": (1, 3, 2), "LLDDDL": (2, 3, 1),
            "LLLDDL": (3, 2, 1), "LDDLLL": (1, 2, 3),
        }

        grouping = format_map.get(pattern)
        if grouping and grouping[2] > 0:
            g1, g2, _ = grouping
            return f"{clean[:g1]}-{clean[g1:g1+g2]}-{clean[g1+g2:]}"

        if len(clean) == 6:
            return f"{clean[:2]}-{clean[2:4]}-{clean[4:]}"

        return clean

    def matches_nl_pattern(self, text: str) -> bool:
        clean = text.replace("-", "").replace(" ", "")
        for pattern, _ in self.NL_PLATE_PATTERNS:
            if pattern.match(clean):
                return True
        return False
