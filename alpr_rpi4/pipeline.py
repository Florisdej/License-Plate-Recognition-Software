"""
ALPR System — Pipeline (RPi4)
==============================
Connects all modules into one processing pipeline:
Detection → Preprocessing → OCR → Output

Adds picamera2 support and a threaded camera method for the web UI.
"""

import cv2
import time
import threading
import numpy as np
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass, field

from detector import PlateDetector, Detection
from preprocessor import PlatePreprocessor
from ocr_engine import PlateOCR
from color_filter import classify_plate_color, filter_by_color
import config

import logging
logger = logging.getLogger(__name__)


@dataclass
class PlateResult:
    """Final result of a license plate recognition."""
    plate_text: str
    detection_confidence: float
    ocr_confidence: float
    bbox: tuple
    cropped_image: np.ndarray
    processed_image: np.ndarray
    plate_color: str = "UNKNOWN"
    timestamp: float = field(default_factory=time.time)

    @property
    def combined_confidence(self) -> float:
        return self.detection_confidence * self.ocr_confidence

    @property
    def label(self) -> str:
        return f"PLATE - {self.plate_color}"

    def __repr__(self):
        return (f"PlateResult(text='{self.plate_text}', "
                f"color={self.plate_color}, "
                f"det_conf={self.detection_confidence:.2f}, "
                f"ocr_conf={self.ocr_confidence:.2f})")


class ALPRPipeline:
    """
    Main ALPR pipeline for RPi4.

    Supports:
      - process_image(path)        — single image file
      - process_frame_array(img)   — numpy array
      - process_video(source)      — file or OpenCV camera index
      - process_picamera2()        — Pi Camera Module via picamera2
      - start_camera_threaded()    — background thread for web UI
    """

    def __init__(self, model_path: Optional[str] = None,
                 log_callback: Optional[Callable] = None,
                 progress_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self._stop_event = threading.Event()

        self._log("=" * 50, "info")
        self._log("  ALPR System — Initialising (RPi4)", "info")
        self._log("=" * 50, "info")

        self._progress("progress_initializing")

        self._log("[Init] Loading detector...", "step")
        self.detector = PlateDetector(model_path)
        self._log("[Init] Detector ready", "success")

        self._log("[Init] Initialising preprocessor...", "step")
        self.preprocessor = PlatePreprocessor()
        self._log("[Init] Preprocessor ready", "success")

        self._log("[Init] Loading OCR engine (EasyOCR)...", "step")
        self.ocr = PlateOCR()
        self._log("[Init] OCR engine ready", "success")

        self.output_dir = Path(config.OUTPUT_DIR)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log(f"[Init] WARNING: Cannot create output dir: {e}", "warning")

        self._log("=" * 50, "info")
        self._log("  ALPR System — Ready!", "success")
        self._log("=" * 50, "info")

    # ------------------------------------------------------------------
    # Logging / progress helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str, level: str = "info"):
        if self.log_callback:
            try:
                self.log_callback(msg, level)
            except Exception:
                pass
        if config.VERBOSE:
            print(msg)

    def _progress(self, step_key: str):
        if self.progress_callback:
            try:
                self.progress_callback(step_key)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public processing methods
    # ------------------------------------------------------------------

    def process_image(self, image_path: str) -> List[PlateResult]:
        """Process a single image file."""
        self._log(f"\n[Pipeline] Processing: {image_path}", "info")
        start_time = time.time()

        image = cv2.imread(image_path)
        if image is None:
            self._log(f"[Pipeline] ERROR: Cannot load image: {image_path}", "error")
            return []

        h, w = image.shape[:2]
        if h < 20 or w < 20:
            self._log(f"[Pipeline] ERROR: Image too small ({w}x{h})", "error")
            return []

        results = self._process_frame(image)

        if results:
            base_name = Path(image_path).stem
            self._save_results(image, results, base_name)

        elapsed = time.time() - start_time
        self._log(f"[Pipeline] Done in {elapsed:.2f}s — {len(results)} plate(s) found",
                  "success")
        return results

    def process_frame_array(self, image: np.ndarray) -> List[PlateResult]:
        """Process a numpy array directly."""
        return self._process_frame(image)

    def process_video(self, video_path, output_path: Optional[str] = None):
        """Process a video file or OpenCV camera (integer index)."""
        self._stop_event.clear()

        if video_path == "0" or video_path == 0:
            cap = cv2.VideoCapture(0)
            self._log("[Pipeline] Camera opened", "info")
        else:
            cap = cv2.VideoCapture(video_path)
            self._log(f"[Pipeline] Video opened: {video_path}", "info")

        if not cap.isOpened():
            self._log("[Pipeline] ERROR: Cannot open video source", "error")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self._log(f"[Pipeline] {width}x{height} @ {fps:.1f}fps ({total_frames} frames)", "info")

        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out_fps = fps / config.VIDEO_FRAME_SKIP
            writer = cv2.VideoWriter(output_path, fourcc, out_fps, (width, height))
            if not writer.isOpened():
                self._log(f"[Pipeline] ERROR: Cannot write to: {output_path}", "error")
                cap.release()
                return

        frame_count = 0
        detection_count = 0
        all_plates = set()

        try:
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                if frame_count % config.VIDEO_FRAME_SKIP != 0:
                    continue

                start_time = time.time()
                results = self._process_frame(frame)
                process_time = time.time() - start_time

                if results:
                    detection_count += len(results)
                    all_plates.update(r.plate_text for r in results)

                    plate_labels = [f"{r.plate_text} [{r.plate_color}]" for r in results]
                    annotated = self.detector.annotate_image(
                        frame,
                        [Detection(r.bbox, r.detection_confidence, r.cropped_image)
                         for r in results],
                        plate_labels,
                    )

                    if writer:
                        writer.write(annotated)

                    progress = ""
                    if total_frames > 0:
                        pct = (frame_count / total_frames) * 100
                        progress = f" [{pct:.0f}%]"

                    for r in results:
                        self._log(
                            f"  Frame {frame_count}{progress}: {r.plate_text} "
                            f"[{r.plate_color}] (det: {r.detection_confidence:.0%}, "
                            f"ocr: {r.ocr_confidence:.0%}) [{process_time*1000:.0f}ms]",
                            "success",
                        )

                    if config.VIDEO_DISPLAY:
                        cv2.imshow("ALPR", annotated)
                elif writer:
                    writer.write(frame)

                if config.VIDEO_DISPLAY:
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        self._log("\n[Pipeline] Stopped by user", "warning")
                        break

        except KeyboardInterrupt:
            self._log("\n[Pipeline] Stopped (Ctrl+C)", "warning")
        finally:
            cap.release()
            if writer:
                writer.release()
            if config.VIDEO_DISPLAY:
                cv2.destroyAllWindows()

        self._log(f"\n{'=' * 50}", "info")
        self._log(f"  Summary", "info")
        self._log(f"  Frames processed: {frame_count}", "info")
        self._log(f"  Total detections: {detection_count}", "info")
        self._log(f"  Unique plates:    {len(all_plates)}", "info")
        if all_plates:
            for plate in sorted(all_plates):
                self._log(f"    → {plate}", "success")
        self._log(f"{'=' * 50}", "info")

    def process_picamera2(self, result_callback: Optional[Callable] = None,
                          frame_callback: Optional[Callable] = None):
        """
        Process frames from the Pi Camera Module via picamera2.

        Args:
            result_callback: Called with each PlateResult as it is produced.
            frame_callback:  Called with the latest annotated BGR frame
                             (bytes from cv2.imencode) — used by the web UI.
        """
        try:
            from picamera2 import Picamera2
        except ImportError:
            self._log("[Pipeline] picamera2 not installed — run: pip install picamera2", "error")
            return

        self._stop_event.clear()
        picam2 = Picamera2()
        cam_config = picam2.create_preview_configuration(
            main={"format": "BGR888", "size": (640, 480)}
        )
        picam2.configure(cam_config)
        picam2.start()
        self._log("[Pipeline] picamera2 started (640x480)", "info")

        frame_count = 0
        try:
            while not self._stop_event.is_set():
                frame = picam2.capture_array()
                frame_count += 1

                if frame_count % config.VIDEO_FRAME_SKIP != 0:
                    continue

                results = self._process_frame(frame)

                if results:
                    plate_labels = [f"{r.plate_text} [{r.plate_color}]" for r in results]
                    annotated = self.detector.annotate_image(
                        frame,
                        [Detection(r.bbox, r.detection_confidence, r.cropped_image)
                         for r in results],
                        plate_labels,
                    )
                    if frame_callback:
                        ok, buf = cv2.imencode(".jpg", annotated,
                                              [cv2.IMWRITE_JPEG_QUALITY, 70])
                        if ok:
                            frame_callback(buf.tobytes())
                    if result_callback:
                        for r in results:
                            result_callback(r)
                else:
                    if frame_callback:
                        ok, buf = cv2.imencode(".jpg", frame,
                                              [cv2.IMWRITE_JPEG_QUALITY, 70])
                        if ok:
                            frame_callback(buf.tobytes())

                if config.VIDEO_DISPLAY:
                    cv2.imshow("ALPR Pi", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        except KeyboardInterrupt:
            self._log("[Pipeline] Stopped (Ctrl+C)", "warning")
        finally:
            picam2.stop()
            if config.VIDEO_DISPLAY:
                cv2.destroyAllWindows()
            self._log("[Pipeline] picamera2 stopped", "info")

    def start_camera_threaded(self, source,
                              result_callback: Optional[Callable] = None,
                              frame_callback: Optional[Callable] = None) -> threading.Thread:
        """
        Run camera in a background daemon thread.

        Args:
            source:          Integer (OpenCV device index) or "picamera2".
            result_callback: Called with each PlateResult.
            frame_callback:  Called with JPEG bytes of each processed frame.

        Returns:
            The started Thread object.
        """
        self._stop_event.clear()

        def _run():
            if source == "picamera2":
                self.process_picamera2(
                    result_callback=result_callback,
                    frame_callback=frame_callback,
                )
            else:
                cap = cv2.VideoCapture(source)
                if not cap.isOpened():
                    self._log(f"[Pipeline] ERROR: Cannot open camera {source}", "error")
                    return

                frame_count = 0
                try:
                    while not self._stop_event.is_set():
                        ret, frame = cap.read()
                        if not ret:
                            break

                        frame_count += 1
                        if frame_count % config.VIDEO_FRAME_SKIP != 0:
                            continue

                        results = self._process_frame(frame)

                        if results:
                            plate_labels = [f"{r.plate_text} [{r.plate_color}]"
                                            for r in results]
                            annotated = self.detector.annotate_image(
                                frame,
                                [Detection(r.bbox, r.detection_confidence, r.cropped_image)
                                 for r in results],
                                plate_labels,
                            )
                            if frame_callback:
                                ok, buf = cv2.imencode(".jpg", annotated,
                                                      [cv2.IMWRITE_JPEG_QUALITY, 70])
                                if ok:
                                    frame_callback(buf.tobytes())
                            if result_callback:
                                for r in results:
                                    result_callback(r)
                        else:
                            if frame_callback:
                                ok, buf = cv2.imencode(".jpg", frame,
                                                      [cv2.IMWRITE_JPEG_QUALITY, 70])
                                if ok:
                                    frame_callback(buf.tobytes())
                finally:
                    cap.release()

        thread = threading.Thread(target=_run, daemon=True, name="alpr-camera")
        thread.start()
        return thread

    def stop_camera(self):
        """Signal the camera thread to stop."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal frame processing
    # ------------------------------------------------------------------

    def _process_frame(self, frame: np.ndarray) -> List[PlateResult]:
        total_start = time.time()

        self._progress("progress_detecting")
        detections = self.detector.detect(frame)

        if not detections:
            self._progress("progress_complete")
            return []

        self._progress("progress_classifying")
        needs_color = config.COLOR_FILTER_ENABLED or config.PLATE_MODE != "all"
        if needs_color:
            plate_colors = [
                classify_plate_color(det.cropped_image, config.COLOR_THRESHOLD)
                for det in detections
            ]
        else:
            plate_colors = ["UNKNOWN"] * len(detections)

        filtered_detections, filtered_colors = filter_by_color(detections, plate_colors)

        results = []
        for idx, (det, color) in enumerate(zip(filtered_detections, filtered_colors)):
            if config.SHARPNESS_MIN_VARIANCE > 0:
                sharpness = self.preprocessor.measure_sharpness(det.cropped_image)
                if sharpness < config.SHARPNESS_MIN_VARIANCE:
                    self._log(
                        f"[Sharpness] Plate {idx+1} skipped (too blurry: {sharpness:.1f})",
                        "warning",
                    )
                    continue

            self._progress("progress_preprocessing")
            variants = self.preprocessor.process_multiple_variants(det.cropped_image)
            processed = variants[0] if variants else det.cropped_image

            self._progress("progress_ocr")
            plate_text, ocr_conf = self.ocr.read_plate_multi(variants)

            if plate_text and len(plate_text) >= 4:
                if config.REQUIRE_NL_PATTERN and not self.ocr.matches_nl_pattern(plate_text):
                    self._log(
                        f"[Pipeline] '{plate_text}' rejected: no valid NL pattern",
                        "warning",
                    )
                    continue

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
        self._log(
            f"[Pipeline] Done: {len(results)} plate(s) in {total_elapsed*1000:.0f}ms",
            "success",
        )
        return results

    def _save_results(self, image: np.ndarray, results: List[PlateResult],
                      base_name: str):
        """Save annotated images and cropped plates to output_dir."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log(f"[Pipeline] ERROR: Cannot create output dir: {e}", "error")
            return

        if config.SAVE_ANNOTATED:
            plate_labels = [f"{r.plate_text} [{r.plate_color}]" for r in results]
            detections = [Detection(r.bbox, r.detection_confidence, r.cropped_image)
                          for r in results]
            try:
                annotated = self.detector.annotate_image(image, detections, plate_labels)
                out_path = self.output_dir / f"{base_name}_annotated.jpg"
                if not cv2.imwrite(str(out_path), annotated):
                    self._log(f"[Pipeline] WARNING: Save failed (disk full?): {out_path}",
                              "warning")
            except Exception as e:
                self._log(f"[Pipeline] ERROR saving annotation: {e}", "error")

        if config.SAVE_CROPPED_PLATES:
            for i, result in enumerate(results):
                crop_path = self.output_dir / f"{base_name}_plate_{i}.jpg"
                proc_path = self.output_dir / f"{base_name}_plate_{i}_processed.jpg"
                try:
                    cv2.imwrite(str(crop_path), result.cropped_image)
                    if result.processed_image is not None:
                        cv2.imwrite(str(proc_path), result.processed_image)
                    self._log(f"[Pipeline] Plate {i} saved: {result.plate_text}", "info")
                except Exception as e:
                    self._log(f"[Pipeline] ERROR saving plate {i}: {e}", "error")
