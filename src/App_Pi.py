#!/usr/bin/env python3
"""
Raspberry Pi optimized version of License Plate Recognition App
- Reduced frame processing rate
- Frame skipping option  
- Smaller display resolution
- OpenVINO optimized inference
"""
import os
import sys

# Add parent directory to path for finding modules when run from src/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "src" else SCRIPT_DIR

import cv2
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFrame, QSizePolicy, QSlider, QStyle, QCheckBox, QSpinBox, QComboBox
)
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QSize, QTimer
from Detect import LicensePlateDetector
from styles import ModernStyles
from Tracker import Tracker


def resource_path(relative_path: str) -> str:
    """Return absolute path to resource, works for development and PyInstaller bundles.
    
    Handles running from both project root and src/ subdirectory.
    """
    base_path = getattr(sys, "_MEIPASS", PROJECT_ROOT)
    return os.path.join(base_path, relative_path)


class LicensePlateAppPi(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("License Plate Recognition - Raspberry Pi")
        self.detector = LicensePlateDetector()
        self.tracker = Tracker(iou_threshold=0.3, timeout_seconds=2.0)
        
        # Set window icon if available (check both old and new paths)
        icon_paths = [
            resource_path("assets/Logo.icns"),
            resource_path("Assets/Logo.icns"),
        ]
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                break

        # Raspberry Pi Optimization Settings
        self.frame_skip_counter = 0
        self.frame_skip_interval = 2  # Process every Nth frame (adjustable)
        self.max_display_width = 640  # Reduce display size for performance
        
        # Camera Settings
        self.max_camera_index = 1  # Scan camera indices 0-1 (Mac typically has 0-1)
        self.available_cameras = []  # List of (index, name) tuples
        self.current_camera_index = 0
        self.camera_retry_attempts = 3
        self.camera_retry_delay = 0.5  # seconds between retries
        
        # Scan for available cameras at startup
        self.scan_cameras()
        
        self.setup_ui()
        self.apply_styles()
        
        # Video Capture State
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.is_camera_active = False
        self.is_video_file_active = False
        self.is_paused = False
        self.total_frames = 0

    def setup_ui(self):
        # Main Layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(24)

        # --- Left Panel: Image Display ---
        left_panel = QVBoxLayout()
        
        # Header
        header_label = QLabel("License Plate Recognition (Pi)")
        header_label.setProperty("class", "header")
        left_panel.addWidget(header_label)

        # Image Container - smaller for Pi
        self.image_label = QLabel("No Image Loaded")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(480, 360)  # Smaller than desktop version
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_panel.addWidget(self.image_label)

        # Playback Controls (Hidden by default)
        self.playback_layout = QHBoxLayout()
        
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_playback)
        self.playback_layout.addWidget(self.play_button)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.sliderMoved.connect(self.set_position)
        self.seek_slider.sliderPressed.connect(self.pause_video)
        self.seek_slider.sliderReleased.connect(self.resume_video)
        self.playback_layout.addWidget(self.seek_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.playback_layout.addWidget(self.time_label)
        
        # Wrap in a widget to easily hide/show
        self.playback_widget = QWidget()
        self.playback_widget.setLayout(self.playback_layout)
        self.playback_widget.hide()
        left_panel.addWidget(self.playback_widget)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.hide()
        left_panel.addWidget(self.progress_bar)

        main_layout.addLayout(left_panel, stretch=2)

        # --- Right Panel: Controls & Results ---
        right_panel = QVBoxLayout()
        right_panel.setSpacing(16)

        # Performance Settings Section (NEW for Pi)
        perf_label = QLabel("Performance Settings")
        perf_label.setProperty("class", "subheader")
        right_panel.addWidget(perf_label)
        
        # Frame skip control
        skip_layout = QHBoxLayout()
        skip_layout.addWidget(QLabel("Process every"))
        self.frame_skip_spinbox = QSpinBox()
        self.frame_skip_spinbox.setMinimum(1)
        self.frame_skip_spinbox.setMaximum(10)
        self.frame_skip_spinbox.setValue(2)
        self.frame_skip_spinbox.setSuffix(" frames")
        self.frame_skip_spinbox.valueChanged.connect(self.update_frame_skip)
        skip_layout.addWidget(self.frame_skip_spinbox)
        right_panel.addLayout(skip_layout)
        
        # FPS info label
        self.fps_label = QLabel("FPS: N/A")
        right_panel.addWidget(self.fps_label)
        
        right_panel.addSpacing(10)

        # Control Section
        controls_label = QLabel("Controls")
        controls_label.setProperty("class", "subheader")
        right_panel.addWidget(controls_label)

        self.load_button = QPushButton("Load Image")
        self.load_button.setIcon(QIcon.fromTheme("document-open"))
        self.load_button.clicked.connect(self.load_image)
        right_panel.addWidget(self.load_button)

        self.load_video_button = QPushButton("Load Video File")
        self.load_video_button.setIcon(QIcon.fromTheme("video-x-generic"))
        self.load_video_button.clicked.connect(self.load_video_file)
        right_panel.addWidget(self.load_video_button)

        self.camera_button = QPushButton("Start Live Feed")
        self.camera_button.setIcon(QIcon.fromTheme("camera-video"))
        self.camera_button.clicked.connect(self.toggle_camera)
        right_panel.addWidget(self.camera_button)

        # Camera Selection Section
        camera_select_layout = QHBoxLayout()
        camera_select_layout.addWidget(QLabel("Camera:"))
        
        self.camera_combobox = QComboBox()
        self.camera_combobox.setMinimumWidth(120)
        self.populate_camera_combobox()
        self.camera_combobox.currentIndexChanged.connect(self.on_camera_selection_changed)
        camera_select_layout.addWidget(self.camera_combobox)
        
        self.refresh_cameras_button = QPushButton("🔄")
        self.refresh_cameras_button.setToolTip("Scan for cameras")
        self.refresh_cameras_button.setMaximumWidth(40)
        self.refresh_cameras_button.clicked.connect(self.refresh_cameras)
        camera_select_layout.addWidget(self.refresh_cameras_button)
        
        right_panel.addLayout(camera_select_layout)

        self.detect_button = QPushButton("Detect License Plate")
        self.detect_button.setIcon(QIcon.fromTheme("system-search"))
        self.detect_button.clicked.connect(self.run_detection)
        self.detect_button.setEnabled(False)
        self.detect_button.setProperty("class", "primary")
        right_panel.addWidget(self.detect_button)

        right_panel.addSpacing(20)

        # Results Section
        results_label = QLabel("Detection Results")
        results_label.setProperty("class", "subheader")
        right_panel.addWidget(results_label)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Class", "Confidence", "Coordinates"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right_panel.addWidget(self.results_table)

        # Status Label
        self.status_label = QLabel("Ready")
        self.status_label.setProperty("class", "status")
        self.status_label.setWordWrap(True)
        right_panel.addWidget(self.status_label)

        main_layout.addLayout(right_panel, stretch=1)
        self.setLayout(main_layout)
        self.resize(900, 600)  # Smaller window for Pi

        # State
        self.current_image_path = None
        self.current_image = None
        
        # FPS tracking
        self.frame_times = []
        self.last_frame_time = None

    def update_frame_skip(self, value):
        """Update frame skip interval from spinbox."""
        self.frame_skip_interval = value

    def apply_styles(self):
        self.setStyleSheet(ModernStyles.get_main_window_style())
        
        # Specific component styling
        self.image_label.setStyleSheet(ModernStyles.get_image_container_style())
        self.results_table.setStyleSheet(ModernStyles.get_table_style())
        self.progress_bar.setStyleSheet(ModernStyles.get_progress_bar_style())
        
        # Button styling
        self.load_button.setStyleSheet(ModernStyles.get_button_style(is_primary=False))
        self.load_video_button.setStyleSheet(ModernStyles.get_button_style(is_primary=False))
        self.camera_button.setStyleSheet(ModernStyles.get_button_style(is_primary=False))
        self.detect_button.setStyleSheet(ModernStyles.get_button_style(is_primary=True))
        self.refresh_cameras_button.setStyleSheet(ModernStyles.get_button_style(is_primary=False))
        
        # Playback controls styling
        self.play_button.setStyleSheet(ModernStyles.get_button_style(is_primary=True))

    def reset_mode(self):
        """Stop any active video/camera and reset UI state."""
        self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.is_camera_active = False
        self.is_video_file_active = False
        self.is_paused = False
        
        self.camera_button.setText("Start Live Feed")
        self.load_button.setEnabled(True)
        self.load_video_button.setEnabled(True)
        self.detect_button.setEnabled(False)
        
        self.playback_widget.hide()
        self.results_table.setRowCount(0)
        self.image_label.setText("No Image Loaded")
        self.status_label.setText("Ready")
        self.fps_label.setText("FPS: N/A")

    def load_image(self):
        self.reset_mode()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        if file_path:
            self.current_image_path = file_path
            self.current_image = cv2.imread(file_path)
            if self.current_image is not None:
                self.display_image(self.current_image)
                self.status_label.setText("Image loaded successfully")
                self.detect_button.setEnabled(True)
                self.results_table.setRowCount(0) # Clear previous results
            else:
                self.status_label.setText("Failed to load image")

    def load_video_file(self):
        self.reset_mode()
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "", "Videos (*.mp4 *.avi *.mov *.mkv)"
        )
        
        if file_path:
            self.cap = cv2.VideoCapture(file_path)
            if not self.cap.isOpened():
                self.status_label.setText("Error: Could not open video file.")
                return

            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.seek_slider.setRange(0, self.total_frames)
            
            self.playback_widget.show()
            self.is_video_file_active = True
            
            # Start paused (better for Pi - user can click play when ready)
            self.is_paused = True
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.status_label.setText("Video loaded. Click play to start.")
            
            # Show first frame
            ret, frame = self.cap.read()
            if ret:
                self.display_image(frame)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # Disable manual detect button during video
            self.detect_button.setEnabled(False)

    def scan_cameras(self):
        """Scan for available cameras (indices 0 through max_camera_index)."""
        self.available_cameras = []
        print(f"[DEBUG] Scanning cameras 0-{self.max_camera_index}...")
        
        for index in range(self.max_camera_index + 1):
            print(f"[DEBUG] Checking camera index {index}...")
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                # Try to read a frame to verify camera is working
                ret, frame = cap.read()
                print(f"[DEBUG] Camera {index}: isOpened=True, read={ret}, frame={'OK' if frame is not None else 'None'}")
                if ret and frame is not None:
                    # Get camera info if available
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    camera_name = f"Camera {index} ({width}x{height})"
                    self.available_cameras.append((index, camera_name))
                    print(f"[DEBUG] Added camera: {camera_name}")
                cap.release()
            else:
                print(f"[DEBUG] Camera {index}: isOpened=False")
        
        # Set default camera index if cameras found
        if self.available_cameras:
            self.current_camera_index = self.available_cameras[0][0]
            print(f"[DEBUG] Default camera set to index {self.current_camera_index}")
        else:
            print("[DEBUG] No cameras found!")
        
        return self.available_cameras

    def populate_camera_combobox(self):
        """Populate the camera dropdown with available cameras."""
        self.camera_combobox.blockSignals(True)
        self.camera_combobox.clear()
        
        if self.available_cameras:
            for index, name in self.available_cameras:
                self.camera_combobox.addItem(name, index)
        else:
            self.camera_combobox.addItem("Geen camera's gevonden", -1)
        
        self.camera_combobox.blockSignals(False)

    def refresh_cameras(self):
        """Refresh the list of available cameras."""
        self.status_label.setText("Scanning for cameras...")
        QApplication.processEvents()
        
        # Stop current camera if active
        was_active = self.is_camera_active
        if was_active:
            self.reset_mode()
        
        # Rescan cameras
        self.scan_cameras()
        self.populate_camera_combobox()
        
        if self.available_cameras:
            camera_count = len(self.available_cameras)
            self.status_label.setText(f"Found {camera_count} camera(s)")
        else:
            self.status_label.setText("No cameras found")

    def on_camera_selection_changed(self, index):
        """Handle camera selection change in dropdown."""
        if index >= 0:
            camera_index = self.camera_combobox.itemData(index)
            if camera_index is not None and camera_index >= 0:
                self.current_camera_index = camera_index
                
                # If camera is currently active, switch to new camera
                if self.is_camera_active:
                    self.switch_camera(camera_index)

    def switch_camera(self, camera_index):
        """Switch to a different camera while live feed is active."""
        # Stop current capture
        self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Try to open new camera with retry logic
        success = self.open_camera_with_retry(camera_index)
        
        if success:
            self.timer.start(100)
            self.status_label.setText(f"Switched to Camera {camera_index}")
        else:
            self.show_camera_error()
            self.is_camera_active = False
            self.camera_button.setText("Start Live Feed")

    def open_camera_with_retry(self, camera_index):
        """Try to open a camera with retry logic.
        
        Returns True if successful, False otherwise.
        """
        for attempt in range(self.camera_retry_attempts):
            self.cap = cv2.VideoCapture(camera_index)
            
            if self.cap.isOpened():
                # Verify by reading a test frame
                ret, _ = self.cap.read()
                if ret:
                    return True
                else:
                    self.cap.release()
            
            # Wait before retry
            if attempt < self.camera_retry_attempts - 1:
                time.sleep(self.camera_retry_delay)
        
        return False

    def show_camera_error(self):
        """Display 'Camera niet gevonden' message in the video window."""
        # Create a black image with error message
        error_img = self.create_error_image("Camera niet gevonden")
        self.display_image(error_img)
        self.status_label.setText("Error: Camera niet gevonden")

    def create_error_image(self, message):
        """Create a black image with centered error message."""
        import numpy as np
        
        # Create black image
        height, width = 360, 480
        img = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        color = (100, 100, 255)  # Light red/orange
        thickness = 2
        
        # Get text size for centering
        (text_width, text_height), _ = cv2.getTextSize(message, font, font_scale, thickness)
        x = (width - text_width) // 2
        y = (height + text_height) // 2
        
        cv2.putText(img, message, (x, y), font, font_scale, color, thickness)
        
        return img

    def toggle_camera(self):
        if not self.is_camera_active:
            # Switching to camera
            self.reset_mode()
            
            # Check if we have cameras available
            if not self.available_cameras:
                self.show_camera_error()
                return
            
            # Get selected camera index from dropdown
            selected_index = self.camera_combobox.currentIndex()
            if selected_index >= 0:
                camera_index = self.camera_combobox.itemData(selected_index)
                if camera_index is not None and camera_index >= 0:
                    self.current_camera_index = camera_index
            
            # Try to open camera with retry logic
            self.status_label.setText("Opening camera...")
            QApplication.processEvents()
            
            success = self.open_camera_with_retry(self.current_camera_index)
            
            if not success:
                self.show_camera_error()
                return
            
            # Slower timer for Pi (100ms = 10 FPS max)
            self.timer.start(100)
            self.is_camera_active = True
            self.camera_button.setText("Stop Live Feed")
            self.load_button.setEnabled(False)
            self.load_video_button.setEnabled(False)
            self.detect_button.setEnabled(False)
            self.status_label.setText(f"Live feed active (Camera {self.current_camera_index})")
        else:
            # Stopping camera
            self.reset_mode()

    def toggle_playback(self):
        if self.is_paused:
            self.resume_video()
        else:
            self.pause_video()

    def pause_video(self):
        self.timer.stop()
        self.is_paused = True
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def resume_video(self):
        # Slower timer for Pi
        self.timer.start(100)  # 10 FPS max
        self.is_paused = False
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def set_position(self, position):
        if self.cap and self.is_video_file_active:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            # Update frame immediately to show seek result
            self.update_frame(single_step=True)

    def update_frame(self, single_step=False):
        if not self.cap:
            print("[DEBUG] update_frame: cap is None")
            return

        ret, frame = self.cap.read()
        print(f"[DEBUG] update_frame: ret={ret}, frame={'OK' if frame is not None else 'None'}")
        if ret and frame is not None:
            # Update slider if playing video file
            if self.is_video_file_active and not single_step:
                current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(current_frame)
                self.seek_slider.blockSignals(False)
                
                # Update time label
                self.time_label.setText(f"{current_frame} / {self.total_frames}")

            # Frame skipping for performance
            self.frame_skip_counter += 1
            should_process = (self.frame_skip_counter % self.frame_skip_interval == 0)
            
            if should_process:
                # Run detection
                try:
                    import time
                    start_time = time.time()
                    
                    result_img, detections = self.detector.detect(frame)
                    active_objects, new_objects = self.tracker.update(detections)
                    
                    # Calculate FPS
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        fps = 1.0 / elapsed
                        self.fps_label.setText(f"FPS: {fps:.1f}")
                    
                    self.display_image(result_img)
                    
                    if new_objects:
                        self.append_results(new_objects)
                        
                except Exception as e:
                    print(f"Detection error: {e}")
                    self.display_image(frame)
            else:
                # Just display without processing
                self.display_image(frame)
        else:
            # End of video file
            if self.is_video_file_active:
                self.pause_video()
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def run_detection(self):
        if self.current_image_path and self.current_image is not None:
            self.status_label.setText("Processing...")
            self.detect_button.setEnabled(False)
            self.load_button.setEnabled(False)
            self.progress_bar.show()
            QApplication.processEvents()
            
            try:
                result_img, detections = self.detector.detect(self.current_image_path)
                
                # Reset tracker for single image and get IDs
                self.tracker.reset()
                active_objects, new_objects = self.tracker.update(detections)
                
                self.display_image(result_img)
                self.results_table.setRowCount(0)
                self.append_results(new_objects)
                self.status_label.setText(f"Detection complete. Found {len(detections)} objects.")
            except Exception as e:
                self.status_label.setText(f"Error: {str(e)}")
            finally:
                self.detect_button.setEnabled(True)
                self.load_button.setEnabled(True)
                self.progress_bar.hide()

    def append_results(self, new_detections):
        current_row = self.results_table.rowCount()
        for det in new_detections:
            self.results_table.insertRow(current_row)
            
            # Display "Plate 1", "Plate 2" etc. using the tracker ID
            plate_label = f"Plate {det['id']}"
            self.results_table.setItem(current_row, 0, QTableWidgetItem(plate_label))
            
            # Confidence
            conf_item = QTableWidgetItem(f"{det['confidence']:.2%}")
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(current_row, 1, conf_item)
            
            # Coordinates
            coords = det['bbox']
            coord_str = f"({int(coords[0])}, {int(coords[1])}) - ({int(coords[2])}, {int(coords[3])})"
            self.results_table.setItem(current_row, 2, QTableWidgetItem(coord_str))
            
            current_row += 1
        
        # Scroll to bottom
        if new_detections:
            self.results_table.scrollToBottom()

    def display_image(self, cv_img):
        # Resize for Pi if needed
        height, width = cv_img.shape[:2]
        if width > self.max_display_width:
            scale = self.max_display_width / width
            new_height = int(height * scale)
            cv_img = cv2.resize(cv_img, (self.max_display_width, new_height))
        
        height, width, channel = cv_img.shape
        bytes_per_line = 3 * width
        q_img = QImage(cv_img.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
        
        # Scale image to fit label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(q_img)
        
        # Get available size
        avail_size = self.image_label.size()
        
        scaled_pixmap = pixmap.scaled(
            avail_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        # Re-scale image on resize if one is loaded
        if self.current_image is not None and not self.is_camera_active:
            self.display_image(self.current_image)
        super().resizeEvent(event)

    def closeEvent(self, event):
        self.reset_mode()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LicensePlateAppPi()
    window.show()
    sys.exit(app.exec())
