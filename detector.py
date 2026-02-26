"""
ALPR Systeem - Detectiemodule
=============================
YOLOv8-gebaseerde kentekendetectie.
Laadt het getrainde model en retourneert bounding boxes met confidence scores.
"""

import logging
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from dataclasses import dataclass
from typing import List, Optional
import config

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Representeert één gedetecteerd kenteken."""
    bbox: tuple          # (x1, y1, x2, y2) - bounding box coördinaten
    confidence: float    # Confidence score (0.0 - 1.0)
    cropped_image: np.ndarray  # Gecropte kentekenregio
    class_name: str = "plate"

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> int:
        return self.width * self.height

    def __repr__(self):
        x1, y1, x2, y2 = self.bbox
        return (f"Detection(bbox=({x1},{y1},{x2},{y2}), "
                f"conf={self.confidence:.2f}, "
                f"size={self.width}x{self.height})")


class PlateDetector:
    """
    Kentekendetector op basis van een getraind YOLOv8-model.

    Gebruik:
        detector = PlateDetector("path/to/best.pt")
        detections = detector.detect(image)
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialiseer de detector.

        Args:
            model_path: Pad naar het .pt modelbestand. Gebruikt config als None.
        """
        config.validate()

        path = model_path or str(config.MODEL_PATH)
        logger.info("[Detector] Model laden: %s", path)

        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(
                f"Model bestand niet gevonden: {path}\n"
                "Controleer MODEL_PATH in config.py."
            )

        try:
            self.model = YOLO(path)
            self.class_names = self.model.names
        except Exception as e:
            raise RuntimeError(f"Kan YOLOv8 model niet laden vanuit '{path}': {e}") from e

        logger.info("[Detector] Model geladen. Klassen: %s", self.class_names)
        logger.info("[Detector] Confidence drempel: %s", config.DETECTION_CONFIDENCE)

    def detect(self, image: np.ndarray) -> List[Detection]:
        """
        Detecteer kentekens in een afbeelding.

        Args:
            image: OpenCV afbeelding (BGR format)

        Returns:
            Lijst van Detection objecten, gesorteerd op confidence (hoog naar laag)
        """
        if image is None or image.size == 0:
            logger.warning("[Detector] Lege afbeelding ontvangen")
            return []

        # Voer detectie uit
        results = self.model(
            image,
            conf=config.DETECTION_CONFIDENCE,
            iou=config.DETECTION_IOU,
            imgsz=config.DETECTION_IMG_SIZE,
            max_det=config.DETECTION_MAX_DETECTIONS,
            verbose=False,
        )

        detections = []

        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue

            for box in result.boxes:
                # Haal bounding box coördinaten op (als integers)
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                class_name = self.class_names.get(class_id, "unknown")

                # Begrens coördinaten tot afbeeldingsgrenzen
                h, w = image.shape[:2]
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)

                # Crop de kentekenregio met een kleine marge
                margin_x = int((x2 - x1) * 0.05)
                margin_y = int((y2 - y1) * 0.1)

                crop_x1 = max(0, x1 - margin_x)
                crop_y1 = max(0, y1 - margin_y)
                crop_x2 = min(w, x2 + margin_x)
                crop_y2 = min(h, y2 + margin_y)

                cropped = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()

                if cropped.size == 0:
                    continue

                detection = Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=confidence,
                    cropped_image=cropped,
                    class_name=class_name,
                )
                detections.append(detection)

        # Sorteer op confidence (hoogste eerst)
        detections.sort(key=lambda d: d.confidence, reverse=True)

        if config.VERBOSE and detections:
            logger.info("[Detector] %d kenteken(s) gevonden", len(detections))

        return detections

    def annotate_image(self, image: np.ndarray, detections: List[Detection],
                       plate_texts: Optional[List[str]] = None) -> np.ndarray:
        """
        Teken bounding boxes en labels op de afbeelding.

        Args:
            image:       Originele afbeelding
            detections:  Lijst van Detection objecten
            plate_texts: Optionele lijst van OCR-resultaten (zelfde volgorde als detections)

        Returns:
            Geannoteerde kopie van de afbeelding
        """
        annotated = image.copy()

        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det.bbox
            color = (0, 255, 0)  # Groen

            # Teken bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Label tekst
            if plate_texts and i < len(plate_texts):
                label = f"{plate_texts[i]} ({det.confidence:.0%})"
            else:
                label = f"{det.class_name} {det.confidence:.0%}"

            # Achtergrond voor tekst
            (text_w, text_h), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
            )
            cv2.rectangle(
                annotated,
                (x1, y1 - text_h - 10),
                (x1 + text_w + 10, y1),
                color, -1
            )

            # Tekst
            cv2.putText(
                annotated, label,
                (x1 + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 0, 0), 2
            )

        return annotated
