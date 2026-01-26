# 🚗 License Plate Recognition - Raspberry Pi Edition

Deze branch bevat de geoptimaliseerde versie voor de Raspberry Pi 4/5, gebruikmakend van **OpenVINO** voor snellere AI-detectie.

## 📋 Projectstructuur
- `src/`: De broncode (geoptimaliseerd voor OpenVINO).
- `models/`: Bevat het `best_openvino_model` (~6.5MB).
- `requirements_pi.txt`: Minimale benodigdheden voor de Pi.

## 🛠 Installatie op de Raspberry Pi

### 1. Systeem Voorbereiding
Draai deze commando's in de terminal van je Pi om de noodzakelijke drivers voor beeldverwerking te installeren:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y libgl1-mesa-glx libglib2.0-0 libopencv-dev
2. Code downloaden

Haal alleen deze specifieke branch binnen:

Bash
git clone -b Clean-Pi-Version [https://github.com/Florisdej/License-Plate-Recognition-Software.git](https://github.com/Florisdej/License-Plate-Recognition-Software.git)
cd License-Plate-Recognition-Software
3. Python Omgeving (Virtual Env)

Het is belangrijk om een virtuele omgeving te gebruiken om conflicten te voorkomen:

Bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_pi.txt
4. Camera Setup

Gebruik je de officiële Pi Camera Module? Zorg dat deze aan staat:

Draai sudo raspi-config.

Ga naar Interface Options -> Legacy Camera -> Enable.

Herstart de Pi.

🚀 De App Starten
Zorg dat je in de venv zit en start de applicatie:

Bash
python3 src/App_Pi.py


### De laatste stappen op je Mac:
1.  **Opslaan:** Sla het bestand op in VS Code.
2.  **GitHub Desktop:** Je ziet de wijziging nu links verschijnen.
3.  **Commit:** Vul in: `Updated README with full installation steps`.
4.  **Push:** Klik op **Push origin**.

Nu heb je niet alleen de code, maar ook de complete handleiding op GitHub staan. Als je straks op de Pi inlogt, hoef je alleen nog maar je eigen README te volgen!

**Zal ik je ook nog helpen met een kort script (`startup.sh`) waarmee je de app met één dubbelklik op je Pi-bureaublad kunt starten?**

