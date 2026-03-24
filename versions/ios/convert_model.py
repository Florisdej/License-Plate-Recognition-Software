"""
ALPR iOS — Model Conversie
===========================
Converteert het YOLOv8 PyTorch model (best.pt) naar Core ML formaat
voor gebruik in de iOS app.

Vereisten:
    pip install ultralytics coremltools

Gebruik:
    python convert_model.py

Output:
    best.mlpackage  (sleep dit in je Xcode-project)
"""

from pathlib import Path
from ultralytics import YOLO

MODEL_PATH = Path(__file__).parent.parent / "model" / "best.pt"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model niet gevonden: {MODEL_PATH}")

print(f"[Conversie] Model laden: {MODEL_PATH}")
model = YOLO(str(MODEL_PATH))

print("[Conversie] Exporteren naar Core ML (dit kan 1-2 minuten duren)...")
export_path = model.export(
    format="coreml",
    nms=True,       # NMS ingebakken in het model (geen naverwerking nodig in Swift)
    imgsz=640,      # Zelfde inputgrootte als Python-config
    half=False,     # Float32 (stabielere iOS compatibiliteit dan float16)
)

print(f"\n[Conversie] Klaar! Output: {export_path}")
print("\nVolgende stap:")
print("  Sleep 'best.mlpackage' in je Xcode-project (zie README.md voor details)")
