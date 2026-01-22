## Quick Start op Raspberry Pi

1. **Systeem Dependencies:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y libgl1-mesa-glx libglib2.0-0 libopencv-dev
Project Setup:

Bash
git clone -b Clean-Pi-Version [https://github.com/Florisdej/License-Plate-Recognition-Software.git](https://github.com/Florisdej/License-Plate-Recognition-Software.git)
cd License-Plate-Recognition-Software
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_pi.txt
Run de App:

Bash
python3 src/App_Pi.py


### Hoe voeg je dit toe?
1.  Open de `README_PI.md` in **VS Code** (zoals in je eerste screenshot).
2.  Plak de bovenstaande tekst erbij onder het hoofdstuk "Installatie".
3.  Sla het bestand op.
4.  Ga naar **GitHub Desktop**, commit de wijziging en druk op **Push origin**.

**Tip voor de Pi:** Omdat je in je screenshot ziet dat OpenCV soms de camera niet kan vinden (`OpenCV: camera failed to properly initialize!`), is het goed om in je README ook te vermelden dat de camera-interface in `sudo raspi-config` aan moet staan.


