"""
ALPR System — Preprocessing Module
=====================================
Image processing of cropped plate regions to maximise OCR readability.

Pipeline: resize → grayscale → denoise → contrast (CLAHE) → sharpen → binarize
"""

import logging
import cv2
import numpy as np
from typing import Optional
import config

logger = logging.getLogger(__name__)


class PlatePreprocessor:
    """
    Processes cropped license plate images for optimal OCR results.

    Each processing step can be individually enabled/disabled via config.py.
    """

    def __init__(self):
        self.clahe = cv2.createCLAHE(
            clipLimit=config.CLAHE_CLIP_LIMIT,
            tileGridSize=config.CLAHE_TILE_SIZE,
        )
        self.sharpen_kernel = np.array([
            [ 0, -1,  0],
            [-1,  5, -1],
            [ 0, -1,  0]
        ], dtype=np.float32)
        self.steps = config.PREPROCESSING

    @staticmethod
    def measure_sharpness(image: np.ndarray) -> float:
        """Laplacian variance — higher = sharper."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def process(self, plate_image: np.ndarray) -> np.ndarray:
        """Run the full preprocessing pipeline."""
        if plate_image is None or plate_image.size == 0:
            return plate_image

        h, w = plate_image.shape[:2]
        if h < 10 or w < 10:
            logger.warning("[Preprocessor] Image too small (%dx%d), skipped", w, h)
            return plate_image

        try:
            img = plate_image.copy()
            if self.steps.get("resize", True):
                img = self._resize(img)
            if self.steps.get("grayscale", True):
                img = self._to_grayscale(img)
            if self.steps.get("denoise", True):
                img = self._denoise(img)
            if self.steps.get("contrast", True):
                img = self._enhance_contrast(img)
            if self.steps.get("sharpen", True):
                img = self._sharpen(img)
            if self.steps.get("binarize", True):
                img = self._binarize(img)
            return img
        except Exception as e:
            logger.warning("[Preprocessor] Pipeline failed (%s), returning original", e)
            return plate_image

    def _resize(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        target_w = config.PLATE_TARGET_WIDTH
        target_h = config.PLATE_TARGET_HEIGHT

        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        if new_w < target_w or new_h < target_h:
            padded = np.ones((target_h, target_w, 3), dtype=np.uint8) * 255
            y_offset = (target_h - new_h) // 2
            x_offset = (target_w - new_w) // 2
            padded[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
            return padded

        return resized

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        return cv2.bilateralFilter(img, 9, 75, 75)

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 2:
            return self.clahe.apply(img)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _sharpen(self, img: np.ndarray) -> np.ndarray:
        return cv2.filter2D(img, -1, self.sharpen_kernel)

    def _binarize(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = img.shape[:2]
        block_size = config.BINARIZE_BLOCK_SIZE
        max_dim = min(h, w)
        if block_size >= max_dim:
            block_size = max(3, max_dim - 1)
        if block_size % 2 == 0:
            block_size -= 1
        if block_size < 3:
            block_size = 3

        try:
            return cv2.adaptiveThreshold(
                img, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                block_size,
                config.BINARIZE_C,
            )
        except Exception as e:
            logger.warning("[Preprocessor] Binarization failed (%s)", e)
            return img

    def process_multiple_variants(self, plate_image: np.ndarray) -> list:
        """
        Generate multiple preprocessing variants for more robust OCR.
        Resize and grayscale are computed once and shared between variants.
        """
        if plate_image is None or plate_image.size == 0:
            return [plate_image]

        try:
            base = self._resize(plate_image.copy())
            base = self._to_grayscale(base)
        except Exception as e:
            logger.warning("[Preprocessor] Base processing failed (%s), using original", e)
            return [plate_image]

        variants = []

        # Variant 1: full pipeline (denoise → contrast → sharpen → adaptive binarize)
        try:
            v1 = self._denoise(base.copy())
            v1 = self._enhance_contrast(v1)
            v1 = self._sharpen(v1)
            v1 = self._binarize(v1)
            variants.append(v1)
        except Exception as e:
            logger.warning("[Preprocessor] Variant 1 failed (%s)", e)
            variants.append(base.copy())

        # Variant 2: contrast only (softer, no binarization)
        try:
            v2 = self._enhance_contrast(base.copy())
            variants.append(v2)
        except Exception as e:
            logger.warning("[Preprocessor] Variant 2 failed (%s)", e)
            variants.append(base.copy())

        # Variant 3: denoise + contrast + Otsu binarization
        try:
            v3 = self._denoise(base.copy())
            v3 = self._enhance_contrast(v3)
            _, v3 = cv2.threshold(v3, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            variants.append(v3)
        except Exception as e:
            logger.warning("[Preprocessor] Variant 3 failed (%s)", e)
            variants.append(base.copy())

        return variants
