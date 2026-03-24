"""
ALPR System — Detection Module (RPi4)
======================================
YOLOv8 license plate detection with ONNX runtime as primary backend
(3-5x faster than PyTorch on ARM) and PyTorch fallback.

ONNX output format expected from `ultralytics export format='onnx'`:
  shape (1, 4+num_classes, num_anchors)
  e.g. for 1-class model at 320x320: (1, 5, 2100)
  columns: [x_center, y_center, width, height, class_conf]
  coordinates are in pixel space of the resized input image.
"""

import logging
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import config

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Represents one detected license plate."""
    bbox: tuple              # (x1, y1, x2, y2)
    confidence: float        # 0.0–1.0
    cropped_image: np.ndarray
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
    License plate detector using ONNX runtime (preferred) or YOLOv8 PyTorch.

    Usage:
        detector = PlateDetector()
        detections = detector.detect(image)
    """

    def __init__(self, model_path: Optional[str] = None):
        config.validate()

        self.onnx_session = None
        self.model = None
        self.class_names = {0: "plate"}

        # --- Try ONNX first ---
        onnx_path = Path(config.ONNX_MODEL_PATH)
        if config.USE_ONNX and onnx_path.exists():
            try:
                import onnxruntime as ort
                self.onnx_session = ort.InferenceSession(
                    str(onnx_path),
                    providers=["CPUExecutionProvider"],
                )
                logger.info("[Detector] ONNX model loaded: %s", onnx_path)
            except Exception as e:
                logger.warning(
                    "[Detector] ONNX load failed (%s), falling back to PyTorch", e
                )
                self.onnx_session = None
        elif config.USE_ONNX and not onnx_path.exists():
            logger.info(
                "[Detector] ONNX model not found at '%s', using PyTorch", onnx_path
            )

        # --- PyTorch fallback ---
        if self.onnx_session is None:
            from ultralytics import YOLO

            path = model_path or str(config.MODEL_PATH)
            path_obj = Path(path)
            if not path_obj.exists():
                raise FileNotFoundError(
                    f"Model file not found: {path}\n"
                    "Run export_onnx.py to create best.onnx, or provide best.pt."
                )
            try:
                self.model = YOLO(path)
                self.class_names = self.model.names
                logger.info("[Detector] PyTorch model loaded: %s", path)
            except Exception as e:
                raise RuntimeError(
                    f"Cannot load YOLOv8 model from '{path}': {e}"
                ) from e

        logger.info(
            "[Detector] Backend: %s | conf=%.2f | imgsz=%d",
            "ONNX" if self.onnx_session else "PyTorch",
            config.DETECTION_CONFIDENCE,
            config.DETECTION_IMG_SIZE,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, image: np.ndarray) -> List[Detection]:
        """
        Detect license plates in an image.

        Args:
            image: OpenCV BGR image

        Returns:
            List of Detection objects sorted by confidence (high → low)
        """
        if image is None or image.size == 0:
            logger.warning("[Detector] Empty image received")
            return []

        if self.onnx_session is not None:
            return self._detect_onnx(image)
        return self._detect_pytorch(image)

    def annotate_image(self, image: np.ndarray, detections: List[Detection],
                       plate_texts: Optional[List[str]] = None) -> np.ndarray:
        """Draw bounding boxes and labels on the image."""
        annotated = image.copy()

        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det.bbox
            color = (0, 255, 0)

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            if plate_texts and i < len(plate_texts):
                label = f"{plate_texts[i]} ({det.confidence:.0%})"
            else:
                label = f"{det.class_name} {det.confidence:.0%}"

            (text_w, text_h), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
            )
            cv2.rectangle(
                annotated,
                (x1, y1 - text_h - 10),
                (x1 + text_w + 10, y1),
                color, -1,
            )
            cv2.putText(
                annotated, label,
                (x1 + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 0, 0), 2,
            )

        return annotated

    # ------------------------------------------------------------------
    # Private: ONNX inference
    # ------------------------------------------------------------------

    def _detect_onnx(self, image: np.ndarray) -> List[Detection]:
        """Run inference via ONNX runtime."""
        orig_h, orig_w = image.shape[:2]
        img_size = config.DETECTION_IMG_SIZE

        # Preprocess: BGR → RGB, resize, HWC → NCHW, normalise [0,1]
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (img_size, img_size), interpolation=cv2.INTER_LINEAR)
        blob = resized.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))   # HWC → CHW
        blob = np.expand_dims(blob, axis=0)     # → NCHW (1,3,H,W)

        # Inference
        input_name = self.onnx_session.get_inputs()[0].name
        outputs = self.onnx_session.run(None, {input_name: blob})

        # Parse output: (1, 4+num_classes, num_anchors) → (num_anchors, 5)
        output = outputs[0][0]   # (5, num_anchors)
        output = output.T        # (num_anchors, 5): [cx, cy, w, h, conf]

        # Filter by confidence threshold
        conf_threshold = config.DETECTION_CONFIDENCE
        mask = output[:, 4] >= conf_threshold
        filtered = output[mask]

        if len(filtered) == 0:
            return []

        # Scale factors from model input → original image
        scale_x = orig_w / img_size
        scale_y = orig_h / img_size

        boxes_xywh = []  # x, y, w, h in original pixel space
        scores = []

        for row in filtered:
            cx, cy, bw, bh, conf = float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4])
            x1 = int((cx - bw / 2) * scale_x)
            y1 = int((cy - bh / 2) * scale_y)
            w  = int(bw * scale_x)
            h  = int(bh * scale_y)
            boxes_xywh.append([x1, y1, w, h])
            scores.append(conf)

        # NMS
        indices = cv2.dnn.NMSBoxes(
            boxes_xywh, scores,
            conf_threshold, config.DETECTION_IOU,
        )

        detections = []
        if len(indices) > 0:
            for idx in np.array(indices).flatten():
                x, y, w, h = boxes_xywh[idx]
                x1, y1, x2, y2 = x, y, x + w, y + h

                # Clamp to image bounds
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(orig_w, x2)
                y2 = min(orig_h, y2)

                if x2 <= x1 or y2 <= y1:
                    continue

                # Crop with small margin
                margin_x = int((x2 - x1) * 0.05)
                margin_y = int((y2 - y1) * 0.10)
                crop_x1 = max(0, x1 - margin_x)
                crop_y1 = max(0, y1 - margin_y)
                crop_x2 = min(orig_w, x2 + margin_x)
                crop_y2 = min(orig_h, y2 + margin_y)

                cropped = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()
                if cropped.size == 0:
                    continue

                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=scores[idx],
                    cropped_image=cropped,
                    class_name="plate",
                ))

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections[:config.DETECTION_MAX_DETECTIONS]

    # ------------------------------------------------------------------
    # Private: PyTorch inference
    # ------------------------------------------------------------------

    def _detect_pytorch(self, image: np.ndarray) -> List[Detection]:
        """Run inference via ultralytics YOLOv8."""
        results = self.model(
            image,
            conf=config.DETECTION_CONFIDENCE,
            iou=config.DETECTION_IOU,
            imgsz=config.DETECTION_IMG_SIZE,
            max_det=config.DETECTION_MAX_DETECTIONS,
            verbose=False,
        )

        detections = []
        h, w = image.shape[:2]

        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                class_name = self.class_names.get(class_id, "unknown")

                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(w, x2); y2 = min(h, y2)

                margin_x = int((x2 - x1) * 0.05)
                margin_y = int((y2 - y1) * 0.10)
                crop_x1 = max(0, x1 - margin_x)
                crop_y1 = max(0, y1 - margin_y)
                crop_x2 = min(w, x2 + margin_x)
                crop_y2 = min(h, y2 + margin_y)

                cropped = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()
                if cropped.size == 0:
                    continue

                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    confidence=confidence,
                    cropped_image=cropped,
                    class_name=class_name,
                ))

        detections.sort(key=lambda d: d.confidence, reverse=True)

        if config.VERBOSE and detections:
            logger.info("[Detector] %d plate(s) found", len(detections))

        return detections
