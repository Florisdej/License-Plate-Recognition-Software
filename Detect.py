import os
import sys
from typing import Dict, List, Tuple

import cv2
from ultralytics import YOLO


def resource_path(relative_path: str) -> str:
    """Return absolute path to resource, works for dev and PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class LicensePlateDetector:
    """Wraps a YOLOv8 model trained to detect license plates and related symbols."""

    def __init__(
        self,
        model_path: str = "models/best.pt",
        confidence_threshold: float = 0.4,
    ):
        resolved_path = resource_path(model_path)
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"Model file not found at '{resolved_path}'.")

        self.confidence_threshold = confidence_threshold
        self.model_path = resolved_path
        self.model = YOLO(self.model_path)
        # Default color map for different classes; extend as needed.
        self.class_colors: Dict[str, Tuple[int, int, int]] = {
            "license_plate": (0, 180, 255),
            "plate_symbol": (80, 220, 100),
            "symbol": (80, 220, 100),
        }

    def detect(self, image_source: str | cv2.Mat) -> Tuple[cv2.Mat, List[Dict[str, float]]]:
        """Run detection and return annotated image plus detection metadata.
        
        Args:
            image_source: Path to image file (str) or loaded image frame (cv2.Mat)
        """
        if isinstance(image_source, str):
            image = cv2.imread(image_source)
            if image is None:
                raise ValueError(f"Unable to read image from path: {image_source}")
        else:
            image = image_source.copy() # Work on a copy to avoid modifying original frame if needed

        if image is None:
             raise ValueError("Invalid image source.")

        results = self.model(image)[0]
        detections: List[Dict[str, float]] = []

        for box in results.boxes:
            confidence = float(box.conf[0])
            if confidence < self.confidence_threshold:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls_id = int(box.cls[0])
            label = results.names.get(cls_id, "license_plate") if isinstance(results.names, dict) else results.names[cls_id]

            detections.append(
                {
                    "label": label,
                    "confidence": confidence,
                    "bbox": (x1, y1, x2, y2),
                }
            )

            # draw bounding box and label
            color = self.class_colors.get(label, (0, 180, 255))
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            text = f"{label} {confidence:.2f}"
            cv2.putText(
                image,
                text,
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )

        return image, detections