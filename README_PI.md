# License Plate Recognition - Raspberry Pi Edition

Een geoptimaliseerde versie van het kenteken herkenningssysteem voor Raspberry Pi 4.

## 🗂️ Projectstructuur

Na het opschonen is de aanbevolen structuur:

```
License-Plate-Recognition/
├── src/
│   ├── App_Pi.py          # Hoofdapplicatie voor Raspberry Pi
│   ├── Detect.py          # Detectiemodule (OpenVINO geoptimaliseerd)
│   ├── Tracker.py         # Object tracking
│   └── styles.py          # GUI styling
├── models/
│   └── best_openvino_model/
│       ├── best.bin       # Model weights (~6MB)
│       ├── best.xml       # Model architectuur
│       └── metadata.yaml  # Model metadata
├── assets/
│   └── Logo.icns          # App icoon
├── requirements_pi.txt    # Dependencies voor Pi
└── README_PI.md           # Deze documentatie
```

## 🚀 Installatie op Raspberry Pi

### 1. Vereisten
- Raspberry Pi 4 (4GB+ RAM aanbevolen)
- Raspberry Pi OS (64-bit aanbevolen voor betere performance)
- Python 3.9+
- Camera module of USB webcam

### 2. Systeem dependencies installeren
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv libgl1-mesa-glx libglib2.0-0
sudo apt install -y libxcb-cursor0 libxkbcommon0  # Voor PyQt6
```

### 3. Project kopiëren
Kopieer de project folder naar je Pi (bijv. via SCP of USB):
```bash
scp -r License-Plate-Recognition/ pi@raspberrypi.local:~/
```

### 4. Virtual environment aanmaken
```bash
cd ~/License-Plate-Recognition
python3 -m venv venv
source venv/bin/activate
```

### 5. Dependencies installeren
```bash
pip install --upgrade pip
pip install -r requirements_pi.txt
```

### 6. Applicatie starten
```bash
cd src
python App_Pi.py
```

## ⚡ Performance Optimizations

Deze versie bevat meerdere optimalisaties voor de Raspberry Pi:

| Optimalisatie | Beschrijving |
|---------------|--------------|
| **OpenVINO Runtime** | Snellere inference dan PyTorch |
| **Kleinere Input Grootte** | `imgsz=320` in plaats van 640 |
| **Frame Skipping** | Verwerk elke N frames (instelbaar) |
| **CPU Optimalisatie** | Expliciet `device='cpu'` |
| **Lagere Display Resolutie** | Minder GPU geheugen nodig |

### Performance verwachtingen

| Instelling | FPS (verwacht) |
|------------|----------------|
| Skip 1 (elk frame) | ~2-3 FPS |
| Skip 2 | ~4-5 FPS |
| Skip 3 | ~6-8 FPS |

## 🔧 Probleemoplossing

### "Model not found" error
Controleer of de models map correct staat:
```bash
ls -la models/best_openvino_model/
# Moet bevatten: best.bin, best.xml, metadata.yaml
```

### PyQt6 errors op Pi
Installeer extra dependencies:
```bash
sudo apt install -y qt6-base-dev
```

### Camera niet gevonden
```bash
# Check of camera werkt
libcamera-hello  # Voor Pi Camera
# Of voor USB camera:
ls /dev/video*
```

### Geheugen problemen
Verhoog swap space:
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile  # Zet CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

## 📝 Gebruik

1. **Start de app**: `python App_Pi.py`
2. **Laad een afbeelding** of start de **Live Feed**
3. Pas **frame skip** aan voor betere performance
4. Bekijk detecties in de resultaten tabel

## 🧹 Opschonen (optioneel)

Om het project verder te verkleinen voor de Pi:

```bash
# Verwijder desktop versie als je die niet nodig hebt
rm App.py app_headless.py

# Verwijder documentatie
rm RASPBERRY_PI_SETUP.md README.md

# Verwijder deployment scripts
rm deploy_to_pi.sh cleanup_for_pi.sh
```

## 📦 Minimale bestandenlijst

De absolute minimum bestanden die je nodig hebt:

```
├── src/App_Pi.py
├── src/Detect.py
├── src/Tracker.py
├── src/styles.py
├── models/best_openvino_model/
└── requirements_pi.txt
```

Totale grootte: ~7MB
