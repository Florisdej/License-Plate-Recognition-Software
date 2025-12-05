# Raspberry Pi Setup Guide for License Plate Recognition App

## Hardware Requirements

### Recommended Hardware
- **Raspberry Pi 4 (4GB or 8GB RAM)** - Minimum recommended
- **Raspberry Pi 5** - Better performance
- **Coral USB Accelerator** - Optional but highly recommended for real-time inference
- **16GB+ microSD card** - For OS and dependencies
- **Active cooling** - Heat sink + fan (YOLO inference generates heat)
- **Power supply** - Official 15W+ USB-C adapter

### Limitations on Raspberry Pi
⚠️ **Performance Considerations:**
- **Raspberry Pi 3/Zero**: NOT recommended - too slow for YOLO inference
- **Raspberry Pi 4 (2GB)**: Marginal - may struggle with video processing
- **Raspberry Pi 4 (4GB+)**: Workable but slower than desktop
- **Raspberry Pi 5**: Best option - significantly faster

## Software Setup

### Step 1: Prepare Your Raspberry Pi

1. **Install Raspberry Pi OS (64-bit)**
   ```bash
   # Use Raspberry Pi Imager to install:
   # - Raspberry Pi OS (64-bit) with desktop
   # Choose the full version (not Lite) for GUI support
   ```

2. **Update the system**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **Install system dependencies**
   ```bash
   sudo apt install -y python3-pip python3-venv python3-dev
   sudo apt install -y libopencv-dev python3-opencv
   sudo apt install -y libqt6widgets6 libqt6gui6 libqt6core6
   sudo apt install -y qt6-base-dev
   sudo apt install -y libatlas-base-dev libhdf5-dev libjasper-dev
   sudo apt install -y libqtgui4 libqtwebkit4 libqt4-test
   sudo apt install -y libavcodec-dev libavformat-dev libswscale-dev
   ```

### Step 2: Transfer Your Application to Raspberry Pi

**Option A: Using SCP (from your Mac)**
```bash
# From your Mac terminal, navigate to the project directory
cd "/Users/florisdejager/Documents/License Plate Recognision Software"

# Transfer to Raspberry Pi (replace 'pi@raspberrypi.local' with your Pi's address)
scp -r . pi@raspberrypi.local:~/license-plate-app/
```

**Option B: Using USB Drive**
1. Copy the entire project folder to a USB drive
2. Plug into Raspberry Pi
3. Copy to home directory

**Option C: Using Git (if you have a repository)**
```bash
# On Raspberry Pi
git clone <your-repo-url> ~/license-plate-app
cd ~/license-plate-app
```

### Step 3: Create Python Virtual Environment

```bash
cd ~/license-plate-app
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Install Python Dependencies

⚠️ **Important**: Installing on Raspberry Pi takes MUCH longer than on Mac (30-60 minutes)

```bash
# Upgrade pip first
pip install --upgrade pip

# Install dependencies one at a time to monitor progress
pip install numpy
pip install opencv-python
pip install PyQt6
pip install ultralytics
```

**If PyQt6 installation fails**, try:
```bash
sudo apt install python3-pyqt6
# Then in your code, you'll use system packages instead of venv
```

### Step 5: Optimize for Raspberry Pi Performance

#### Option A: Use Lighter YOLO Model
The current YOLOv8n model might be too heavy. Consider:

```bash
# Download YOLOv8n-nano (smallest, fastest)
# You're already using this - good!

# Or use INT8 quantized model for even faster inference
# (You may need to quantize your custom model)
```

#### Option B: Setup Coral USB Accelerator (Optional)
If you have a Coral USB Accelerator for hardware acceleration:

```bash
# Follow Coral setup guide
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt update
sudo apt install libedgetpu1-std python3-pycoral
```

You'll need to convert your model to TFLite format.

### Step 6: Configure Display Settings

For PyQt6 GUI to work properly:

```bash
# Enable X11 forwarding if running headless (optional)
export DISPLAY=:0

# Add to ~/.bashrc to make permanent
echo 'export DISPLAY=:0' >> ~/.bashrc
```

### Step 7: Run the Application

```bash
cd ~/license-plate-app
source venv/bin/activate
python3 App.py
```

## Performance Optimization Tips

### 1. **Reduce Frame Rate for Video**
In `App.py`, change line 239 and 256:
```python
# Current: self.timer.start(30)  # ~33 FPS
# Change to: 
self.timer.start(100)  # ~10 FPS - more manageable for Pi
```

### 2. **Reduce Frame Size**
Process smaller frames to speed up inference:

In `Detect.py`, resize before detection:
```python
# In detect() method, after reading image:
MAX_WIDTH = 640
if image.shape[1] > MAX_WIDTH:
    scale = MAX_WIDTH / image.shape[1]
    new_height = int(image.shape[0] * scale)
    image = cv2.resize(image, (MAX_WIDTH, new_height))
```

### 3. **Skip Frames**
Process every Nth frame instead of every frame:

```python
# Add frame counter in App.py __init__:
self.frame_counter = 0
self.process_every_n_frames = 3  # Process every 3rd frame

# In update_frame():
self.frame_counter += 1
if self.frame_counter % self.process_every_n_frames != 0:
    # Just display, don't process
    self.display_image(frame)
    return
```

### 4. **Use Headless Mode for Camera-Only**
If you don't need the GUI and just want to process camera feed:
- Create a minimal version without PyQt6
- Output results to terminal or file
- Much faster!

## Troubleshooting

### Issue: "ImportError: No module named 'PyQt6'"
**Solution**: Install system PyQt6
```bash
sudo apt install python3-pyqt6
```

### Issue: "Illegal instruction" or crashes
**Solution**: You might have installed x86 wheels. Rebuild from source:
```bash
pip uninstall opencv-python
pip install opencv-python --no-binary opencv-python
```

### Issue: Very slow inference (>5 seconds per frame)
**Solutions**:
1. Use smaller input images (resize to 416x416 or 320x320)
2. Skip frames (process every 2nd or 3rd frame)
3. Use FP16 or INT8 quantized model
4. Consider Coral USB Accelerator

### Issue: Out of memory errors
**Solutions**:
```bash
# Increase swap size
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change CONF_SWAPSIZE=100 to CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### Issue: Camera not detected
**Solutions**:
```bash
# Enable camera in raspi-config
sudo raspi-config
# Navigate to: Interface Options > Camera > Enable

# For USB cameras, check:
ls /dev/video*

# If camera is at /dev/video1 instead of /dev/video0,
# change line 251 in App.py to: self.cap = cv2.VideoCapture(1)
```

## Alternative: Headless/Server Mode

If the GUI is too heavy, create a lightweight server version:

### Create `app_headless.py`:
```python
#!/usr/bin/env python3
import cv2
from Detect import LicensePlateDetector
from Tracker import Tracker

def main():
    detector = LicensePlateDetector()
    tracker = Tracker()
    cap = cv2.VideoCapture(0)
    
    print("Starting license plate detection...")
    print("Press 'q' to quit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        result_img, detections = detector.detect(frame)
        active_objects, new_objects = tracker.update(detections)
        
        if new_objects:
            for obj in new_objects:
                print(f"Detected Plate {obj['id']}: {obj['confidence']:.2%}")
        
        cv2.imshow('License Plate Detection', result_img)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
```

Run with:
```bash
python3 app_headless.py
```

## Expected Performance Benchmarks

| Raspberry Pi Model | FPS (YOLOv8n) | Usability |
|-------------------|---------------|-----------|
| Pi 3B+ | 0.5-1 FPS | ❌ Too slow |
| Pi 4 (2GB) | 1-2 FPS | ⚠️ Barely usable |
| Pi 4 (4GB) | 2-4 FPS | ✅ Workable |
| Pi 4 (8GB) | 3-5 FPS | ✅ Good |
| Pi 5 (4GB) | 5-8 FPS | ✅ Very good |
| Pi 5 + Coral | 15-30 FPS | ✅ Excellent |

## Next Steps

1. **Test on Pi 4/5**: Start with image processing first (not video)
2. **Benchmark**: Measure actual FPS on your specific hardware
3. **Optimize**: Apply frame skipping and resizing as needed
4. **Consider Hardware Acceleration**: Coral USB if real-time is critical

## Remote Access (Optional)

To run the GUI remotely from your Mac:

```bash
# On Mac, SSH with X11 forwarding:
ssh -X pi@raspberrypi.local

# Then run the app:
cd ~/license-plate-app
source venv/bin/activate
python3 App.py
```

Or use VNC for full remote desktop.

---

**Questions?** Check the troubleshooting section or create an issue in your project repository.
