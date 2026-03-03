# ALPR iOS — Standalone iPhone App

Offline kentekenherkenning voor iPhone. Alle verwerking draait op het apparaat zelf — geen server of internetverbinding vereist.

**Vereisten:**
- Mac met Xcode 15 of nieuwer
- iPhone met iOS 16 of nieuwer
- Python 3.x met `ultralytics` geïnstalleerd (eenmalig, voor modelconversie)

---

## Stap 1 — Model converteren

Voer dit eenmalig uit vanuit de `alpr_ios/` map:

```bash
pip install ultralytics coremltools
python convert_model.py
```

Dit genereert `best.mlpackage` naast dit bestand (~30–50 MB).

---

## Stap 2 — Xcode-project aanmaken

1. Open Xcode → **File → New → Project**
2. Kies **iOS → App**
3. Instellingen:
   - **Product Name:** `ALPR`
   - **Interface:** SwiftUI
   - **Language:** Swift
   - Kies een locatie op je schijf en klik **Create**

---

## Stap 3 — Swift-bestanden toevoegen

1. Verwijder het automatisch aangemaakte `ContentView.swift` en `ALPRApp.swift` uit het Xcode-project (verplaats naar prullenbak)
2. Sleep alle bestanden uit `alpr_ios/Sources/` naar de Xcode-projectnavigator:
   - `ALPRApp.swift`
   - `ContentView.swift`
   - `CameraManager.swift`
   - `PlateDetector.swift`
   - `PlateOCR.swift`
   - `PlatePreprocessor.swift`
   - `PlateResult.swift`
3. Zorg dat **"Copy items if needed"** is aangevinkt en de juiste target geselecteerd is

---

## Stap 4 — Core ML model toevoegen

1. Sleep `best.mlpackage` (gegenereerd in Stap 1) naar de Xcode-projectnavigator
2. Zorg dat **"Copy items if needed"** aangevinkt is
3. Xcode compileert het model automatisch naar `best.mlmodelc` bij het builden

---

## Stap 5 — Camera-permissie instellen

1. Klik op het project (blauw icoon) in de navigator → selecteer de **ALPR** target → tab **Info**
2. Voeg een nieuwe key toe:
   - **Key:** `NSCameraUsageDescription`
- **Value:** `Deze app gebruikt de camera voor kentekenherkenning.`

---

## Stap 6 — App op iPhone deployen

1. Sluit je iPhone aan via USB
2. Selecteer je iPhone als build-target (bovenin Xcode)
3. Klik **▶ Run** (of `Cmd+R`)
4. Bij de eerste keer: ga op je iPhone naar **Instellingen → Algemeen → VPN & Apparaatbeheer** en vertrouw je developer-account

---

## Architectuur

```
iPhone
├── CameraManager         — AVCaptureSession, frame-delegate
├── PlateDetector         — Core ML (YOLOv8) bounding box detectie
│   ├── PlatePreprocessor — CoreImage: grayscale, contrast, scherp
│   └── PlateOCR          — Vision (VNRecognizeTextRequest) + NL patronen
└── ContentView           — SwiftUI interface (camera preview + resultatenlijst)
```

| Component | iOS equivalent van Python |
|---|---|
| `CameraManager` | `cv2.VideoCapture` |
| `PlateDetector` | `detector.py` (YOLOv8) |
| `PlatePreprocessor` | `preprocessor.py` (OpenCV) |
| `PlateOCR` | `ocr_engine.py` (EasyOCR) |
| Vision framework | EasyOCR |
| Core ML | ultralytics YOLO |

---

## Veelvoorkomende problemen

**App bouwt niet — "best.mlmodelc niet gevonden"**
→ Controleer of `best.mlpackage` aan het project is toegevoegd (Stap 4)

**Camera-scherm is leeg / permissie gevraagd maar geen toegang**
→ Ga naar iPhone Instellingen → Privacy & Beveiliging → Camera → zet ALPR aan

**Geen kentekens herkend**
→ Houd het kenteken zo stil mogelijk; scherptefilter slaat wazige frames over
→ Zorg voor voldoende belichting; Vision OCR heeft moeite in het donker

**Buitenlandse kentekens worden niet herkend**
→ `PlateOCR.swift` valideert alleen NL-patronen (12 sidecodes).
   Voeg extra patronen toe aan `nlPatterns` voor andere landen.
