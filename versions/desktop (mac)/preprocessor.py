"""
ALPR Systeem - Preprocessingmodule
===================================
Beeldverwerking van gecropte kentekenregio's om OCR-leesbaarheid te maximaliseren.

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
    Verwerkt gecropte kentekenafbeeldingen voor optimale OCR-resultaten.

    Elke verwerkingsstap kan individueel worden in-/uitgeschakeld via config.py.
    """

    def __init__(self):
        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        self.clahe = cv2.createCLAHE(
            clipLimit=config.CLAHE_CLIP_LIMIT,
            tileGridSize=config.CLAHE_TILE_SIZE,
        )

        # Verscherpingskernel
        self.sharpen_kernel = np.array([
            [ 0, -1,  0],
            [-1,  5, -1],
            [ 0, -1,  0]
        ], dtype=np.float32)

        self.steps = config.PREPROCESSING

    @staticmethod
    def measure_sharpness(image: np.ndarray) -> float:
        """
        Meet de scherpte van een afbeelding via de Laplacian-variantie.

        Hogere waarde = scherper beeld. Nuttig als filter voor wazige live-cameraframes.

        Args:
            image: Afbeelding (BGR of grayscale)

        Returns:
            Laplacian-variantie (float). Waarden < 80 duiden op wazigheid.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def process(self, plate_image: np.ndarray) -> np.ndarray:
        """
        Voer de volledige preprocessingpipeline uit.

        Args:
            plate_image: Gecropte kentekenafbeelding (BGR)

        Returns:
            Verwerkte afbeelding, geoptimaliseerd voor OCR
        """
        if plate_image is None or plate_image.size == 0:
            return plate_image

        h, w = plate_image.shape[:2]
        if h < 10 or w < 10:
            logger.warning("[Preprocessor] Afbeelding te klein (%dx%d), overgeslagen", w, h)
            return plate_image

        try:
            img = plate_image.copy()

            # Stap 1: Resize naar consistente grootte
            if self.steps.get("resize", True):
                img = self._resize(img)

            # Stap 2: Converteer naar grijswaarden
            if self.steps.get("grayscale", True):
                img = self._to_grayscale(img)

            # Stap 3: Ruisreductie
            if self.steps.get("denoise", True):
                img = self._denoise(img)

            # Stap 4: Contrastverhoging
            if self.steps.get("contrast", True):
                img = self._enhance_contrast(img)

            # Stap 5: Verscherping
            if self.steps.get("sharpen", True):
                img = self._sharpen(img)

            # Stap 6: Binarisatie
            if self.steps.get("binarize", True):
                img = self._binarize(img)

            return img
        except Exception as e:
            logger.warning("[Preprocessor] Preprocessing mislukt (%s), origineel teruggestuurd", e)
            return plate_image

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """Schaal de afbeelding naar de doelgrootte met behoud van aspect ratio."""
        h, w = img.shape[:2]
        target_w = config.PLATE_TARGET_WIDTH
        target_h = config.PLATE_TARGET_HEIGHT

        # Bereken schaalfactor (behoud aspect ratio)
        scale = min(target_w / w, target_h / h)

        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Pad met witte rand als nodig
        if new_w < target_w or new_h < target_h:
            padded = np.ones((target_h, target_w, 3), dtype=np.uint8) * 255
            y_offset = (target_h - new_h) // 2
            x_offset = (target_w - new_w) // 2
            padded[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
            return padded

        return resized

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        """Converteer naar grijswaarden."""
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        """Verwijder ruis (gebruikt snellere methoden dan fastNlMeans)."""
        # Bilateral Filter is veel sneller en behoudt randen beter
        if len(img.shape) == 2:
            return cv2.bilateralFilter(img, 9, 75, 75)
        else:
            return cv2.bilateralFilter(img, 9, 75, 75)

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        """Verhoog contrast met CLAHE."""
        if len(img.shape) == 2:
            return self.clahe.apply(img)
        else:
            # Pas CLAHE toe op het luminantiekanaal (LAB-kleurruimte)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _sharpen(self, img: np.ndarray) -> np.ndarray:
        """Verscherp de afbeelding."""
        return cv2.filter2D(img, -1, self.sharpen_kernel)

    def _binarize(self, img: np.ndarray) -> np.ndarray:
        """Pas adaptieve binarisatie toe."""
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = img.shape[:2]
        block_size = config.BINARIZE_BLOCK_SIZE

        # Block size mag de afbeeldingsafmetingen niet overschrijden
        max_dim = min(h, w)
        if block_size >= max_dim:
            block_size = max(3, max_dim - 1)

        # Block size moet oneven zijn
        if block_size % 2 == 0:
            block_size -= 1
        if block_size < 3:
            block_size = 3

        try:
            binary = cv2.adaptiveThreshold(
                img,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                block_size,
                config.BINARIZE_C,
            )
            return binary
        except Exception as e:
            logger.warning("[Preprocessor] Binarisatie mislukt (%s), grijswaardenafbeelding teruggestuurd", e)
            return img

    def process_multiple_variants(self, plate_image: np.ndarray) -> list:
        """
        Genereer meerdere preprocessingvarianten voor robuustere OCR.

        Resize en grayscale worden eenmalig berekend en gedeeld tussen varianten
        om redundante berekeningen te vermijden (~50% minder preprocessing werk).

        Args:
            plate_image: Gecropte kentekenafbeelding (BGR)

        Returns:
            Lijst van verwerkte afbeeldingen
        """
        if plate_image is None or plate_image.size == 0:
            return [plate_image]

        # Gedeelde basisstappen: resize + grayscale (eenmalig berekend)
        try:
            base = self._resize(plate_image.copy())
            base = self._to_grayscale(base)
        except Exception as e:
            logger.warning("[Preprocessor] Basisverwerking mislukt (%s), origineel gebruikt", e)
            return [plate_image]

        variants = []

        # Variant 1: Volledige pipeline (denoise → contrast → sharpen → adaptive binarize)
        try:
            v1 = self._denoise(base.copy())
            v1 = self._enhance_contrast(v1)
            v1 = self._sharpen(v1)
            v1 = self._binarize(v1)
            variants.append(v1)
        except Exception as e:
            logger.warning("[Preprocessor] Variant 1 mislukt (%s)", e)
            variants.append(base.copy())

        # Variant 2: Alleen contrast (geen binarisatie, zachter resultaat)
        try:
            v2 = self._enhance_contrast(base.copy())
            variants.append(v2)
        except Exception as e:
            logger.warning("[Preprocessor] Variant 2 mislukt (%s)", e)
            variants.append(base.copy())

        # Variant 3: Denoise + contrast + Otsu-binarisatie
        try:
            v3 = self._denoise(base.copy())
            v3 = self._enhance_contrast(v3)
            _, v3 = cv2.threshold(v3, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            variants.append(v3)
        except Exception as e:
            logger.warning("[Preprocessor] Variant 3 mislukt (%s)", e)
            variants.append(base.copy())

        return variants
