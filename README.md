# License Plate Recognition Software

A PyQt6-based GUI application for detecting and tracking license plates using YOLO object detection.

## Features

- 📸 **Live camera feed** processing
- 🎥 **Video file** analysis with playback controls
- 🖼️ **Static image** detection
- 🎯 **Object tracking** with unique plate IDs
- ⏯️ **Playback controls** (play/pause, seek, spacebar shortcuts)
- 📊 **Detection results table** with confidence scores
- 🎨 **Modern UI** with PyQt6

## Platform Support

### Desktop (Mac/Windows/Linux)
Run the standard version:
```bash
python3 App.py
```

### Raspberry Pi
For better performance on Raspberry Pi, use the optimized version:
```bash
python3 App_Pi.py
```

The Pi version includes:
- Frame skipping controls
- Reduced display resolution
- FPS monitoring
- Performance optimizations

## Quick Start

### Prerequisites
- Python 3.8+
- Webcam (for live feed)
- YOLO model file in `Models/` directory

### Installation

1. **Clone or download this repository**

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r Requirements.txt
   ```

4. **Run the application:**
   ```bash
   # Desktop version
   python3 App.py
   
   # Or Pi-optimized version
   python3 App_Pi.py
   ```

## Raspberry Pi Deployment

### Quick Deploy Script

Use the automated deployment script to transfer files to your Pi:

```bash
./deploy_to_pi.sh pi@raspberrypi.local
```

### Manual Setup

See **[RASPBERRY_PI_SETUP.md](RASPBERRY_PI_SETUP.md)** for detailed instructions including:
- Hardware requirements
- System dependencies
- Performance optimization
- Troubleshooting

## Usage

### Loading Media
1. **Load Image** - Process a single image file
2. **Load Video File** - Analyze a video file with playback controls
3. **Start Live Feed** - Use your webcam for real-time detection

### Playback Controls
- **Spacebar** - Play/pause video
- **Seek bar** - Jump to any frame
- **Play button** - Toggle playback

### Detection
- **Automatic** - Continuous detection during video/camera feed
- **Manual** - Click "Detect License Plate" for static images

## Project Structure

```
.
├── App.py                    # Main desktop application
├── App_Pi.py                 # Raspberry Pi optimized version
├── Detect.py                 # YOLO detection wrapper
├── Tracker.py                # Object tracking logic
├── styles.py                 # UI styling
├── Requirements.txt          # Python dependencies
├── RASPBERRY_PI_SETUP.md     # Pi deployment guide
├── deploy_to_pi.sh          # Automated Pi deployment script
├── Models/                   # YOLO model files
│   └── best.pt
├── Assets/                   # Icons and resources
│   └── Logo.icns
└── Data.yaml                 # Dataset configuration
```

## Performance Tips

### Desktop
- Works smoothly with default settings
- Real-time processing at 20-30 FPS

### Raspberry Pi
- **Pi 4 (4GB+)**: 2-5 FPS with optimizations
- **Pi 5**: 5-8 FPS
- **With Coral USB**: 15-30 FPS

**Optimization options in App_Pi.py:**
- Adjust "Process every N frames" slider
- Lower values = better performance, less frequent detection
- Higher values = more detections, slower performance

## Keyboard Shortcuts

- **Spacebar** - Play/pause video playback
- **ESC** - (Future) Stop camera feed

## Requirements

### Python Packages
- opencv-python >= 4.8.0
- PyQt6 >= 6.5.0
- ultralytics >= 8.0.0
- numpy >= 1.24.0
- scipy >= 1.11.0

### System Requirements
- **Desktop**: Any modern computer with webcam
- **Raspberry Pi**: Pi 4 (4GB+) or Pi 5 recommended

## Troubleshooting

### "No module named 'PyQt6'"
```bash
pip install PyQt6
# Or on Raspberry Pi:
sudo apt install python3-pyqt6
```

### "Could not open camera"
- Check camera permissions
- On Pi: Enable camera in `sudo raspi-config`
- Try different camera index: Change `cv2.VideoCapture(0)` to `cv2.VideoCapture(1)`

### Slow performance on Raspberry Pi
- Use `App_Pi.py` instead of `App.py`
- Increase frame skip interval
- See RASPBERRY_PI_SETUP.md for more optimizations

## Development

Built with:
- **YOLOv8/v11** - Object detection
- **PyQt6** - GUI framework
- **OpenCV** - Image/video processing
- **Custom tracker** - Multi-object tracking with IOU

## License

[Your license here]

## Author

Floris de Jager

## Support

For issues or questions:
1. Check RASPBERRY_PI_SETUP.md for Pi-specific issues
2. Review error messages in terminal
3. Verify all dependencies are installed
