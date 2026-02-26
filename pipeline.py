"""
ALPR Systeem - Pipeline
========================
Verbindt alle modules tot één doorlopende verwerkingspipeline:
Detectie → Preprocessing → OCR → Output

Ondersteunt een log_callback voor integratie met de GUI dev console.
"""

import cv2
import time
import numpy as np
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass, field

from detector import PlateDetector, Detection
from preprocessor import PlatePreprocessor
from ocr_engine import PlateOCR
from color_filter import classify_plate_color, filter_by_color
import config


@dataclass
class PlateResult:
    """Eindresultaat van een kentekenherkenning."""
    plate_text: str              # Herkende kentekentekst
    detection_confidence: float  # YOLO detectie confidence
    ocr_confidence: float        # OCR herkennings confidence
    bbox: tuple                  # Bounding box (x1, y1, x2, y2)
    cropped_image: np.ndarray    # Gecropte kentekenregio
    processed_image: np.ndarray  # Voorverwerkte afbeelding (voor OCR)
    plate_color: str = "UNKNOWN" # Kleurclassificatie ("BLUE", "YELLOW", "UNKNOWN")
    timestamp: float = field(default_factory=time.time)

    @property
    def combined_confidence(self) -> float:
        """Gecombineerde confidence score."""
        return self.detection_confidence * self.ocr_confidence

    @property
    def label(self) -> str:
        """Label voor weergave: 'PLATE - BLUE', 'PLATE - YELLOW', etc."""
        return f"PLATE - {self.plate_color}"

    def __repr__(self):
        return (f"PlateResult(text='{self.plate_text}', "
                f"color={self.plate_color}, "
                f"det_conf={self.detection_confidence:.2f}, "
                f"ocr_conf={self.ocr_confidence:.2f})")


class ALPRPipeline:
    """
    Hoofdpipeline voor Automatic License Plate Recognition.

    Verwerkt afbeeldingen en video door de volledige keten:
    1. Kentekendetectie (YOLOv8)
    2. Beeldvoorverwerking (OpenCV)
    3. Tekstherkenning (EasyOCR)

    Gebruik:
        pipeline = ALPRPipeline("path/to/best.pt")
        results = pipeline.process_image("path/to/image.jpg")
        pipeline.process_video("path/to/video.mp4")
    """

    def __init__(self, model_path: Optional[str] = None,
                 log_callback: Optional[Callable] = None,
                 progress_callback: Optional[Callable] = None):
        """
        Initialiseer alle modules.

        Args:
            model_path:        Pad naar YOLOv8 model. Gebruikt config.MODEL_PATH als None.
            log_callback:      Optionele callback(msg, level) voor dev console logging.
                               Levels: "info", "success", "warning", "error", "step"
            progress_callback: Optionele callback(step_key) voor voortgangsindicatie.
                               Stappen: "progress_detecting", "progress_classifying",
                                        "progress_preprocessing", "progress_ocr",
                                        "progress_complete"
        """
        self.log_callback = log_callback
        self.progress_callback = progress_callback

        self._log("=" * 50, "info")
        self._log("  ALPR Systeem - Initialisatie", "info")
        self._log("=" * 50, "info")

        self._progress("progress_initializing")

        self._log("[Init] Detector laden (YOLOv8)...", "step")
        self.detector = PlateDetector(model_path)
        self._log("[Init] Detector geladen", "success")

        self._log("[Init] Preprocessor initialiseren...", "step")
        self.preprocessor = PlatePreprocessor()
        self._log("[Init] Preprocessor gereed", "success")

        self._log("[Init] OCR engine laden (EasyOCR)...", "step")
        self.ocr = PlateOCR()
        self._log("[Init] OCR engine gereed", "success")

        # Output directory
        self.output_dir = Path(config.OUTPUT_DIR)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log(f"[Init] WAARSCHUWING: Kan output map niet aanmaken: {e}", "warning")

        self._log("=" * 50, "info")
        self._log("  ALPR Systeem - Gereed!", "success")
        self._log("=" * 50, "info")

    def _log(self, msg: str, level: str = "info"):
        """Log een bericht naar de callback en stdout."""
        if self.log_callback:
            try:
                self.log_callback(msg, level)
            except Exception:
                pass
        if config.VERBOSE:
            print(msg)

    def _progress(self, step_key: str):
        """Meld voortgang aan de GUI."""
        if self.progress_callback:
            try:
                self.progress_callback(step_key)
            except Exception:
                pass

    def process_image(self, image_path: str) -> List[PlateResult]:
        """
        Verwerk een enkele afbeelding.

        Args:
            image_path: Pad naar de afbeelding

        Returns:
            Lijst van PlateResult objecten
        """
        self._log(f"\n[Pipeline] Verwerken: {image_path}", "info")
        start_time = time.time()

        # Laad afbeelding
        image = cv2.imread(image_path)
        if image is None:
            self._log(f"[Pipeline] FOUT: Kan afbeelding niet laden: {image_path}", "error")
            return []

        h, w = image.shape[:2]
        if h < 20 or w < 20:
            self._log(f"[Pipeline] FOUT: Afbeelding te klein ({w}x{h}): {image_path}", "error")
            return []

        # Verwerk
        results = self._process_frame(image)

        # Sla resultaten op
        if results:
            base_name = Path(image_path).stem
            self._save_results(image, results, base_name)

        elapsed = time.time() - start_time
        self._log(f"[Pipeline] Klaar in {elapsed:.2f}s - "
                  f"{len(results)} kenteken(s) gevonden", "success")

        return results

    def process_frame_array(self, image: np.ndarray) -> List[PlateResult]:
        """
        Verwerk een afbeelding als numpy array (voor integratie met andere systemen).

        Args:
            image: OpenCV afbeelding (BGR)

        Returns:
            Lijst van PlateResult objecten
        """
        return self._process_frame(image)

    def process_video(self, video_path: str, output_path: Optional[str] = None):
        """
        Verwerk een videobestand frame-voor-frame.

        Args:
            video_path:  Pad naar het videobestand (of 0 voor webcam)
            output_path: Optioneel pad voor output video
        """
        # Open video
        if video_path == "0" or video_path == 0:
            cap = cv2.VideoCapture(0)
            self._log("[Pipeline] Camera geopend", "info")
        else:
            cap = cv2.VideoCapture(video_path)
            self._log(f"[Pipeline] Video geopend: {video_path}", "info")

        if not cap.isOpened():
            self._log("[Pipeline] FOUT: Kan video niet openen", "error")
            return

        # Video eigenschappen
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self._log(f"[Pipeline] Video: {width}x{height} @ {fps:.1f}fps "
                  f"({total_frames} frames)", "info")
        self._log(f"[Pipeline] Frame skip: elke {config.VIDEO_FRAME_SKIP}e frame", "info")

        # Output video writer
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out_fps = fps / config.VIDEO_FRAME_SKIP
            writer = cv2.VideoWriter(output_path, fourcc, out_fps, (width, height))
            if not writer.isOpened():
                self._log(f"[Pipeline] FOUT: Kan output video niet schrijven naar: {output_path}", "error")
                cap.release()
                return
            self._log(f"[Pipeline] Output video: {output_path}", "info")

        frame_count = 0
        detection_count = 0
        all_plates = set()

        self._log("\n[Pipeline] Verwerking gestart... (Ctrl+C om te stoppen)\n", "info")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                # Skip frames voor performance
                if frame_count % config.VIDEO_FRAME_SKIP != 0:
                    continue

                # Verwerk frame
                start_time = time.time()
                results = self._process_frame(frame)
                process_time = time.time() - start_time

                if results:
                    detection_count += len(results)
                    plate_texts = [r.plate_text for r in results]
                    all_plates.update(plate_texts)

                    # Annoteer frame (met kleurlabel)
                    plate_labels = [
                        f"{r.plate_text} [{r.plate_color}]" for r in results
                    ]
                    annotated = self.detector.annotate_image(
                        frame,
                        [Detection(r.bbox, r.detection_confidence,
                                   r.cropped_image) for r in results],
                        plate_labels,
                    )

                    # Schrijf naar output video
                    if writer:
                        writer.write(annotated)

                    # Print resultaten
                    progress = ""
                    if total_frames > 0:
                        pct = (frame_count / total_frames) * 100
                        progress = f" [{pct:.0f}%]"

                    for r in results:
                        self._log(f"  Frame {frame_count}{progress}: "
                                  f"{r.plate_text} [{r.plate_color}] "
                                  f"(det: {r.detection_confidence:.0%}, "
                                  f"ocr: {r.ocr_confidence:.0%}) "
                                  f"[{process_time*1000:.0f}ms]", "success")

                    # Toon preview als gewenst
                    if config.VIDEO_DISPLAY:
                        cv2.imshow("ALPR", annotated)
                elif writer:
                    writer.write(frame)

                # Check voor toetsaanslag (quit met 'q')
                if config.VIDEO_DISPLAY:
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        self._log("\n[Pipeline] Gestopt door gebruiker", "warning")
                        break

        except KeyboardInterrupt:
            self._log("\n[Pipeline] Gestopt door gebruiker (Ctrl+C)", "warning")

        finally:
            cap.release()
            if writer:
                writer.release()
            if config.VIDEO_DISPLAY:
                cv2.destroyAllWindows()

        # Samenvatting
        self._log(f"\n{'=' * 50}", "info")
        self._log(f"  Video Samenvatting", "info")
        self._log(f"{'=' * 50}", "info")
        self._log(f"  Frames verwerkt:  {frame_count}", "info")
        self._log(f"  Detecties totaal: {detection_count}", "info")
        self._log(f"  Unieke kentekens: {len(all_plates)}", "info")
        if all_plates:
            self._log(f"  Gevonden:", "success")
            for plate in sorted(all_plates):
                self._log(f"    → {plate}", "success")
        self._log(f"{'=' * 50}", "info")

    def _process_frame(self, frame: np.ndarray) -> List[PlateResult]:
        """
        Interne verwerking van een enkel frame.

        Pipeline: Detectie → Kleurclassificatie → Kleurfilter → Preprocessing → OCR

        Args:
            frame: OpenCV afbeelding (BGR)

        Returns:
            Lijst van PlateResult objecten (gefilterd op kleur indien ingeschakeld)
        """
        total_start = time.time()

        # Stap 1: Detectie
        self._progress("progress_detecting")
        self._log(f"[Detectie] Start op frame {frame.shape[1]}x{frame.shape[0]}", "step")
        t0 = time.time()
        detections = self.detector.detect(frame)
        t1 = time.time()
        self._log(f"[Detectie] {len(detections)} plaat/platen gevonden in {(t1-t0)*1000:.0f}ms", "info")

        if not detections:
            self._log("[Detectie] Geen kentekens gevonden", "warning")
            self._progress("progress_complete")
            return []

        # Stap 2: Classificeer kleur (alleen als kleurfilter actief is of PLATE_MODE specifiek is)
        self._progress("progress_classifying")
        needs_color = config.COLOR_FILTER_ENABLED or config.PLATE_MODE != "all"
        if needs_color:
            self._log(f"[Kleur] Classificatie van {len(detections)} detectie(s)...", "step")
            t2 = time.time()
            plate_colors = [
                classify_plate_color(det.cropped_image, config.COLOR_THRESHOLD)
                for det in detections
            ]
            t3 = time.time()
            for i, (det, color) in enumerate(zip(detections, plate_colors)):
                conf_str = f"{det.confidence:.0%}"
                self._log(f"  Plaat {i+1}: kleur={color}, conf={conf_str}", "info")
            self._log(f"[Kleur] Classificatie klaar in {(t3-t2)*1000:.0f}ms", "info")
        else:
            plate_colors = ["UNKNOWN"] * len(detections)
            self._log("[Kleur] Kleurclassificatie overgeslagen (niet ingeschakeld)", "info")

        # Stap 3: Filter op kleur (afhankelijk van config)
        filtered_detections, filtered_colors = filter_by_color(detections, plate_colors)
        if len(filtered_detections) < len(detections):
            diff = len(detections) - len(filtered_detections)
            self._log(f"[Filter] {diff} detectie(s) weggefilterd (modus: {config.PLATE_MODE})", "warning")

        # Stap 4: Preprocessing + OCR op gefilterde detecties
        results = []
        for idx, (det, color) in enumerate(zip(filtered_detections, filtered_colors)):
            # Preprocessing (meerdere varianten)
            self._progress("progress_preprocessing")
            self._log(f"[Preprocessing] Plaat {idx+1}: varianten genereren...", "step")
            t4 = time.time()
            variants = self.preprocessor.process_multiple_variants(det.cropped_image)
            t5 = time.time()
            processed = variants[0] if variants else det.cropped_image
            self._log(f"[Preprocessing] {len(variants)} varianten in {(t5-t4)*1000:.0f}ms", "info")

            # OCR (probeer alle varianten)
            self._progress("progress_ocr")
            self._log(f"[OCR] Plaat {idx+1}: tekst herkennen...", "step")
            t6 = time.time()
            plate_text, ocr_conf = self.ocr.read_plate_multi(variants)
            t7 = time.time()
            self._log(f"[OCR] Resultaat: '{plate_text}' (conf: {ocr_conf:.2f}) in {(t7-t6)*1000:.0f}ms",
                      "success" if plate_text and len(plate_text) >= 4 else "warning")

            if plate_text and len(plate_text) >= 4:
                result = PlateResult(
                    plate_text=plate_text,
                    detection_confidence=det.confidence,
                    ocr_confidence=ocr_conf,
                    bbox=det.bbox,
                    cropped_image=det.cropped_image,
                    processed_image=processed,
                    plate_color=color,
                )
                results.append(result)

        total_elapsed = time.time() - total_start
        self._progress("progress_complete")
        self._log(f"[Pipeline] Klaar: {len(results)} kenteken(s) herkend in {total_elapsed*1000:.0f}ms", "success")

        return results

    def _save_results(self, image: np.ndarray, results: List[PlateResult],
                      base_name: str):
        """Sla geannoteerde afbeeldingen en gecropte kentekens op."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log(f"[Pipeline] FOUT: Kan output map niet aanmaken: {e}", "error")
            return

        if config.SAVE_ANNOTATED:
            plate_labels = [
                f"{r.plate_text} [{r.plate_color}]" for r in results
            ]
            detections = [
                Detection(r.bbox, r.detection_confidence, r.cropped_image)
                for r in results
            ]
            try:
                annotated = self.detector.annotate_image(image, detections, plate_labels)
                out_path = self.output_dir / f"{base_name}_annotated.jpg"
                if not cv2.imwrite(str(out_path), annotated):
                    self._log(f"[Pipeline] WAARSCHUWING: Opslaan mislukt (schijf vol?): {out_path}", "warning")
                else:
                    self._log(f"[Pipeline] Geannoteerd opgeslagen: {out_path}", "info")
            except Exception as e:
                self._log(f"[Pipeline] FOUT bij opslaan annotatie: {e}", "error")

        if config.SAVE_CROPPED_PLATES:
            for i, result in enumerate(results):
                crop_path = self.output_dir / f"{base_name}_plate_{i}.jpg"
                proc_path = self.output_dir / f"{base_name}_plate_{i}_processed.jpg"
                try:
                    if not cv2.imwrite(str(crop_path), result.cropped_image):
                        self._log(f"[Pipeline] WAARSCHUWING: Crop opslaan mislukt: {crop_path}", "warning")
                    if result.processed_image is not None and not cv2.imwrite(str(proc_path), result.processed_image):
                        self._log(f"[Pipeline] WAARSCHUWING: Processed opslaan mislukt: {proc_path}", "warning")
                    self._log(f"[Pipeline] Kenteken {i} opgeslagen: {result.plate_text}", "info")
                except Exception as e:
                    self._log(f"[Pipeline] FOUT bij opslaan kenteken {i}: {e}", "error")
