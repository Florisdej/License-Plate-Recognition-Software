#!/usr/bin/env python3
"""
ALPR System — RPi4 CLI Entry Point
=====================================
Headless-first: no GUI, ONNX inference, optional web dashboard.

Usage:
    Single image:
        python main.py --image photo.jpg

    Image directory:
        python main.py --image-dir ./photos/

    Video file:
        python main.py --video video.mp4

    Webcam (headless):
        python main.py --camera 0 --no-display

    Webcam + web dashboard (built-in):
        python main.py --camera 0 --web

    Webcam + modern SPA frontend:
        python main.py --camera 0 --web --frontend ./frontend

    Pi Camera Module + web dashboard:
        python main.py --picamera2 --web

    Systemd service (suppresses console output):
        python main.py --camera 0 --web --service
"""

import argparse
import logging
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pipeline import ALPRPipeline
import config

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="ALPR System — RPi4 License Plate Recognition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --image plate.jpg
  %(prog)s --image-dir ./photos/
  %(prog)s --video parking.mp4
  %(prog)s --camera 0 --web
  %(prog)s --picamera2 --web --service
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--image", "-i", nargs="+",
                             help="Image file(s) to process")
    input_group.add_argument("--image-dir", "-d",
                             help="Directory of images to process")
    input_group.add_argument("--video", "-v",
                             help="Video file path")
    input_group.add_argument("--camera", "-c", type=int, metavar="DEVICE",
                             help="OpenCV camera device index (e.g. 0)")
    input_group.add_argument("--picamera2", action="store_true",
                             help="Use Pi Camera Module via picamera2")

    parser.add_argument("--model", "-m", default=None,
                        help=f"Path to YOLOv8 .pt model (default: {config.MODEL_PATH})")
    parser.add_argument("--confidence", type=float, default=config.DETECTION_CONFIDENCE,
                        help=f"Detection confidence threshold (default: {config.DETECTION_CONFIDENCE})")
    parser.add_argument("--frame-skip", type=int, default=config.VIDEO_FRAME_SKIP,
                        help=f"Process every Nth frame (default: {config.VIDEO_FRAME_SKIP})")
    parser.add_argument("--no-display", action="store_true",
                        help="Disable live OpenCV preview (headless/SSH)")
    parser.add_argument("--output-video", help="Path for annotated output video")
    parser.add_argument("--output-dir", "-o", default=str(config.OUTPUT_DIR),
                        help=f"Output directory (default: {config.OUTPUT_DIR})")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not save any output images")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Minimal output (plates only)")

    # RPi4-specific flags
    parser.add_argument("--web", action="store_true",
                        help="Start Flask web dashboard on http://0.0.0.0:5000")
    parser.add_argument("--web-port", type=int, default=config.WEB_UI_PORT,
                        help=f"Web UI port (default: {config.WEB_UI_PORT})")
    parser.add_argument("--frontend", metavar="DIR", default=None,
                        help="Path to SPA frontend directory (e.g. ./frontend). "
                             "Serves the modern dashboard instead of the built-in one. "
                             "Requires --web.")
    parser.add_argument("--service", action="store_true",
                        help="Suppress console output (for systemd service)")

    return parser.parse_args()


def process_images(pipeline: ALPRPipeline, image_paths: list):
    all_results = {}
    for path in image_paths:
        if not Path(path).exists():
            logger.warning("File not found: %s", path)
            continue
        results = pipeline.process_image(path)
        all_results[path] = results
    return all_results


def process_image_dir(pipeline: ALPRPipeline, dir_path: str):
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    image_dir = Path(dir_path)
    if not image_dir.is_dir():
        logger.warning("Directory not found: %s", dir_path)
        return {}
    image_paths = sorted([str(f) for f in image_dir.iterdir()
                          if f.suffix.lower() in extensions])
    if not image_paths:
        logger.warning("No images found in: %s", dir_path)
        return {}
    logger.info("%d images found in %s", len(image_paths), dir_path)
    return process_images(pipeline, image_paths)


def print_summary(all_results: dict):
    print(f"\n{'=' * 60}")
    print(f"  Results")
    print(f"{'=' * 60}")
    total_detections = 0
    unique_plates = set()
    for path, results in all_results.items():
        filename = Path(path).name
        if results:
            for r in results:
                total_detections += 1
                unique_plates.add(r.plate_text)
                print(f"  {filename}: {r.plate_text} "
                      f"(det: {r.detection_confidence:.0%}, "
                      f"ocr: {r.ocr_confidence:.0%})")
        else:
            print(f"  {filename}: no plate found")
    print(f"\n  Total detections:  {total_detections}")
    print(f"  Unique plates:     {len(unique_plates)}")
    if unique_plates:
        for plate in sorted(unique_plates):
            print(f"    → {plate}")
    print(f"{'=' * 60}")


def main():
    args = parse_args()

    # Suppress console output when running as systemd service
    if args.service:
        config.VERBOSE = False

    config.setup_logging()

    # Apply CLI overrides
    config.DETECTION_CONFIDENCE = args.confidence
    config.VIDEO_FRAME_SKIP = args.frame_skip
    config.OUTPUT_DIR = Path(args.output_dir)
    config.SAVE_CROPPED_PLATES = not args.no_save
    config.SAVE_ANNOTATED = not args.no_save
    config.VERBOSE = not args.quiet and not args.service
    config.WEB_UI_PORT = args.web_port

    if args.no_display:
        config.VIDEO_DISPLAY = False

    pipeline = ALPRPipeline(args.model)
    start_time = time.time()

    # --- Static image modes (no web UI needed) ---
    if args.image:
        all_results = process_images(pipeline, args.image)
        print_summary(all_results)

    elif args.image_dir:
        all_results = process_image_dir(pipeline, args.image_dir)
        print_summary(all_results)

    elif args.video:
        pipeline.process_video(args.video, args.output_video)

    # --- Live camera modes ---
    elif args.camera is not None or args.picamera2:
        if args.web:
            # Import web_ui and wire up shared state
            from web_ui import create_app, push_frame, push_result

            app = create_app(frontend_dir=args.frontend)

            # Start Flask in a daemon thread
            flask_thread = threading.Thread(
                target=lambda: app.run(
                    host=config.WEB_UI_HOST,
                    port=config.WEB_UI_PORT,
                    threaded=True,
                    use_reloader=False,
                ),
                daemon=True,
                name="flask",
            )
            flask_thread.start()
            logger.info(
                "Web dashboard: http://%s:%d", config.WEB_UI_HOST, config.WEB_UI_PORT
            )
            if not args.service:
                print(f"[ALPR] Web dashboard: http://0.0.0.0:{config.WEB_UI_PORT}")

            source = "picamera2" if args.picamera2 else args.camera
            pipeline.start_camera_threaded(
                source,
                result_callback=push_result,
                frame_callback=push_frame,
            )

            # Block main thread
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pipeline.stop_camera()
                logger.info("[ALPR] Stopped")

        else:
            # No web UI — run in main thread
            if args.picamera2:
                pipeline.process_picamera2()
            else:
                pipeline.process_video(args.camera, args.output_video)

    total_time = time.time() - start_time
    logger.info("Total runtime: %.2fs", total_time)


if __name__ == "__main__":
    main()
