#!/usr/bin/env python3
"""
ALPR System — ONNX Exporter
==============================
Convert a trained YOLOv8 .pt model to ONNX format for faster RPi4 inference.

Usage:
    python export_onnx.py --model model/best.pt
    python export_onnx.py --model model/best.pt --imgsz 320 --output model/best.onnx
"""

import argparse
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export YOLOv8 .pt model to ONNX",
    )
    parser.add_argument("--model", required=True,
                        help="Path to YOLOv8 .pt model file")
    parser.add_argument("--imgsz", type=int, default=320,
                        help="Input image size for the exported model (default: 320)")
    parser.add_argument("--output", default=None,
                        help="Output .onnx path (default: same dir as model, .onnx suffix)")
    return parser.parse_args()


def main():
    args = parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[ERROR] Model not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else model_path.with_suffix(".onnx")

    print(f"[Export] Loading model: {model_path}")
    print(f"[Export] Input size:    {args.imgsz}x{args.imgsz}")
    print(f"[Export] Output:        {output_path}")

    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] ultralytics not installed: pip install ultralytics", file=sys.stderr)
        sys.exit(1)

    model = YOLO(str(model_path))

    exported = model.export(
        format="onnx",
        imgsz=args.imgsz,
        simplify=True,
        opset=12,
    )

    # ultralytics returns the path of the exported file
    exported_path = Path(exported) if exported else output_path

    # Rename to desired output path if different
    if exported_path.exists() and exported_path != output_path:
        exported_path.rename(output_path)
        exported_path = output_path

    size_mb = exported_path.stat().st_size / 1_000_000
    print(f"\n[Export] Done!")
    print(f"[Export] File:  {exported_path}")
    print(f"[Export] Size:  {size_mb:.1f} MB")
    print(f"\nCopy to RPi4 and set ONNX_MODEL_PATH in config.py.")


if __name__ == "__main__":
    main()
