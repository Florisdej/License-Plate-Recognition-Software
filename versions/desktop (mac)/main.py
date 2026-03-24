#!/usr/bin/env python3
"""
ALPR Systeem - Hoofdapplicatie
================================
Automatic License Plate Recognition

Gebruik:
    Enkele afbeelding:
        python main.py --image foto.jpg

    Meerdere afbeeldingen:
        python main.py --image foto1.jpg foto2.jpg foto3.jpg

    Map met afbeeldingen:
        python main.py --image-dir ./fotos/

    Videobestand:
        python main.py --video video.mp4

    Live camera:
        python main.py --camera

    Met aangepast model:
        python main.py --model pad/naar/best.pt --image foto.jpg
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Voeg project root toe aan path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import ALPRPipeline
import config

logger = logging.getLogger(__name__)


def parse_args():
    """Verwerk command-line argumenten."""
    parser = argparse.ArgumentParser(
        description="ALPR Systeem - Automatische Kentekenherkenning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Voorbeelden:
  %(prog)s --image kenteken.jpg
  %(prog)s --image-dir ./fotos/
  %(prog)s --video parkeerplaats.mp4
  %(prog)s --camera
  %(prog)s --image foto.jpg --confidence 0.6 --no-save
        """,
    )

    # Invoerbronnen (onderling exclusief)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--image", "-i",
        nargs="+",
        help="Pad(en) naar afbeelding(en) om te verwerken",
    )
    input_group.add_argument(
        "--image-dir", "-d",
        help="Map met afbeeldingen om te verwerken",
    )
    input_group.add_argument(
        "--video", "-v",
        help="Pad naar videobestand",
    )
    input_group.add_argument(
        "--camera", "-c",
        action="store_true",
        help="Gebruik live camera (webcam / Pi camera)",
    )

    # Model opties
    parser.add_argument(
        "--model", "-m",
        default=None,
        help=f"Pad naar YOLOv8 model (standaard: {config.MODEL_PATH})",
    )

    # Detectie-instellingen
    parser.add_argument(
        "--confidence",
        type=float,
        default=config.DETECTION_CONFIDENCE,
        help=f"Minimale detectie confidence (standaard: {config.DETECTION_CONFIDENCE})",
    )

    # Video-instellingen
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=config.VIDEO_FRAME_SKIP,
        help=f"Verwerk elke N-de frame (standaard: {config.VIDEO_FRAME_SKIP})",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Geen live preview tonen (voor SSH/headless)",
    )
    parser.add_argument(
        "--output-video",
        help="Pad voor output video met annotaties",
    )

    # Output-instellingen
    parser.add_argument(
        "--output-dir", "-o",
        default=str(config.OUTPUT_DIR),
        help=f"Output directory (standaard: {config.OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Sla geen afbeeldingen op",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimale output (alleen kentekens)",
    )

    return parser.parse_args()


def process_images(pipeline: ALPRPipeline, image_paths: list):
    """Verwerk een lijst van afbeeldingen."""
    all_results = {}

    for path in image_paths:
        if not Path(path).exists():
            logger.warning("Bestand niet gevonden: %s", path)
            continue

        results = pipeline.process_image(path)
        all_results[path] = results

    return all_results


def process_image_dir(pipeline: ALPRPipeline, dir_path: str):
    """Verwerk alle afbeeldingen in een map."""
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    image_dir = Path(dir_path)

    if not image_dir.is_dir():
        logger.warning("Map niet gevonden: %s", dir_path)
        return {}

    image_paths = sorted([
        str(f) for f in image_dir.iterdir()
        if f.suffix.lower() in extensions
    ])

    if not image_paths:
        logger.warning("Geen afbeeldingen gevonden in: %s", dir_path)
        return {}

    logger.info("%d afbeeldingen gevonden in %s", len(image_paths), dir_path)
    return process_images(pipeline, image_paths)


def print_summary(all_results: dict):
    """Print een overzicht van alle resultaten."""
    print(f"\n{'=' * 60}")
    print(f"  Resultaten Overzicht")
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
            print(f"  {filename}: geen kenteken gevonden")

    print(f"\n  Totaal detecties:  {total_detections}")
    print(f"  Unieke kentekens:  {len(unique_plates)}")
    if unique_plates:
        print(f"\n  Alle gevonden kentekens:")
        for plate in sorted(unique_plates):
            print(f"    → {plate}")
    print(f"{'=' * 60}")


def main():
    """Hoofdfunctie."""
    args = parse_args()

    # Initialiseer logging voor het hele systeem
    config.setup_logging()

    # Pas configuratie aan op basis van argumenten
    config.DETECTION_CONFIDENCE = args.confidence
    config.VIDEO_FRAME_SKIP = args.frame_skip
    config.OUTPUT_DIR = Path(args.output_dir)
    config.SAVE_CROPPED_PLATES = not args.no_save
    config.SAVE_ANNOTATED = not args.no_save
    config.VERBOSE = not args.quiet

    if args.no_display:
        config.VIDEO_DISPLAY = False

    # Initialiseer pipeline
    pipeline = ALPRPipeline(args.model)

    # Verwerk invoer
    start_time = time.time()

    if args.image:
        all_results = process_images(pipeline, args.image)
        print_summary(all_results)

    elif args.image_dir:
        all_results = process_image_dir(pipeline, args.image_dir)
        print_summary(all_results)

    elif args.video:
        pipeline.process_video(args.video, args.output_video)

    elif args.camera:
        pipeline.process_video(0, args.output_video)

    total_time = time.time() - start_time
    logger.info("Totale verwerkingstijd: %.2fs", total_time)


if __name__ == "__main__":
    main()
