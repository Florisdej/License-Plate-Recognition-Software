# ALPR Systeem — Automatische Kentekenherkenning

Automatic License Plate Recognition systeem op basis van YOLOv8 en EasyOCR, geoptimaliseerd voor Raspberry Pi 4.

## Architectuur

```
Invoer (afbeelding/video)
        │
        ▼
┌─────────────────┐
│   YOLOv8        │  → Detecteert kentekenregio's (bounding boxes)
│   Detectie      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Preprocessing  │  → Contrast, ruisreductie, binarisatie
│  (OpenCV)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   EasyOCR       │  → Leest tekst uit kenteken
│   Herkenning    │
└────────┬────────┘
         │
         ▼
    Resultaat (tekst + confidence)
```

## Projectstructuur

```
alpr_system/
├── main.py            # CLI entry point
├── gui.py             # Grafische interface (CustomTkinter)
├── config.py          # Alle configuratie-instellingen
├── detector.py        # YOLOv8 kentekendetectie
├── preprocessor.py    # Beeldvoorverwerking voor OCR
├── ocr_engine.py      # EasyOCR integratie + NL-kentekenformattering
├── pipeline.py        # Verbindt alle modules
├── requirements.txt   # Python dependencies
├── setup_pi.sh        # Raspberry Pi installatescript
├── model/
│   └── best.pt        # Jouw getrainde YOLOv8 model
└── output/            # Resultaten (geannoteerde afbeeldingen)
```

## Installatie

### Raspberry Pi 4 (aanbevolen)

```bash
# 1. Clone of kopieer het project naar je Pi
scp -r alpr_system/ pi@<pi-ip>:~/

# 2. Maak het setup script uitvoerbaar en draai het
cd ~/alpr_system
chmod +x setup_pi.sh
./setup_pi.sh

# 3. Plaats je model
mkdir -p model
cp /pad/naar/best.pt model/best.pt
```

### Andere systemen (macOS/Linux/Windows)

```bash
# Maak een virtuele omgeving
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Installeer dependencies
pip install -r requirements.txt

# Plaats je model
mkdir -p model
cp /pad/naar/best.pt model/best.pt
```

## Gebruik

### GUI (grafische interface)

```bash
python gui.py
```

Met een specifiek model:

```bash
python gui.py --model pad/naar/best.pt
```

De GUI biedt vier pagina's: **Afbeeldingen** (laden en analyseren van foto's), **Video / Camera** (live verwerking met bounding boxes), **Geschiedenis** (overzicht van alle detecties met CSV-export), en **Instellingen** (confidence drempels, preprocessing stappen, model wissel).

### Enkele afbeelding (CLI)

```bash
python main.py --image foto.jpg
```

### Meerdere afbeeldingen

```bash
python main.py --image foto1.jpg foto2.jpg foto3.jpg
```

### Map met afbeeldingen

```bash
python main.py --image-dir ./fotos/
```

### Videobestand

```bash
python main.py --video parkeerplaats.mp4
```

### Live camera (Pi Camera / USB webcam)

```bash
python main.py --camera
```

### Headless modus (via SSH, zonder display)

```bash
python main.py --video video.mp4 --no-display
```

### Output video met annotaties

```bash
python main.py --video input.mp4 --output-video output.mp4
```

## Opties

| Optie | Kort | Beschrijving |
|-------|------|-------------|
| `--image` | `-i` | Afbeelding(en) om te verwerken |
| `--image-dir` | `-d` | Map met afbeeldingen |
| `--video` | `-v` | Videobestand |
| `--camera` | `-c` | Live camera |
| `--model` | `-m` | Pad naar YOLOv8 model |
| `--confidence` | | Min. detectie confidence (standaard: 0.5) |
| `--frame-skip` | | Verwerk elke N-de frame (standaard: 3) |
| `--no-display` | | Geen preview venster |
| `--output-video` | | Pad voor output video |
| `--output-dir` | `-o` | Output directory |
| `--no-save` | | Sla geen afbeeldingen op |
| `--quiet` | `-q` | Minimale output |

## Configuratie

Alle instellingen staan in `config.py`. De belangrijkste:

- **DETECTION_CONFIDENCE**: Minimale score om een kenteken te accepteren (0.0 - 1.0)
- **PREPROCESSING**: Schakel individuele verwerkingsstappen in/uit
- **VIDEO_FRAME_SKIP**: Hoger = sneller maar minder frames verwerkt
- **OCR_GPU**: Zet op `False` voor Raspberry Pi

## Tips voor Raspberry Pi

1. Gebruik `--frame-skip 5` of hoger voor soepelere verwerking
2. Gebruik `--no-display` bij SSH-sessies
3. Start met `--confidence 0.4` als er weinig detecties zijn
4. De eerste run is langzamer (EasyOCR downloadt taalmodellen)
5. Overweeg `opencv-python-headless` i.p.v. `opencv-python` voor minder dependencies
