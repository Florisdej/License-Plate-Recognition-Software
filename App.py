import os
import sys
import cv2
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFrame, QSizePolicy, QSlider, QStyle, QComboBox
)
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QSize, QTimer
from Detect import LicensePlateDetector
from styles import ModernStyles
from Tracker import Tracker

def resource_path(relative_path: str) -> str:
    """Return absolute path to resource, works for development and PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def enumerate_cameras(max_cameras=10):
    """Enumerate available camera devices with their names."""
    available_cameras = []
    
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # Try to get camera name/description
            # On macOS, index 0 is usually the built-in camera
            backend_name = cap.getBackendName()
            
            # Get basic info to create a descriptive name
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            
            if i == 0:
                camera_name = f"Built-in Camera ({int(width)}x{int(height)})"
            else:
                camera_name = f"External Camera {i} ({int(width)}x{int(height)})"
            
            available_cameras.append((i, camera_name))
            cap.release()
        else:
            # Stop checking after first unavailable camera
            break
    
    return available_cameras

class LicensePlateApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("License Plate Recognition")
        self.detector = LicensePlateDetector()
        self.tracker = Tracker(iou_threshold=0.3, timeout_seconds=2.0)
        
        # Set window icon if available
        icon_path = resource_path("Assets/Logo.icns")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setup_ui()
        self.apply_styles()
        
        # Video Capture State
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
        header_label = QLabel("License Plate Recognition")
        header_label.setProperty("class", "header")
        left_panel.addWidget(header_label)

        # Image Container
        self.image_label = QLabel("No Image Loaded")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
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

        # Camera selection layout (horizontal: dropdown + button)
        camera_layout = QHBoxLayout()
        camera_layout.setSpacing(8)
        
        self.camera_dropdown = QComboBox()
        self.camera_dropdown.setMinimumWidth(200)
        self.camera_dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.populate_camera_list()
        camera_layout.addWidget(self.camera_dropdown, stretch=2)
        
        self.camera_button = QPushButton("Start Live Feed")
        self.camera_button.setIcon(QIcon.fromTheme("camera-video"))
        self.camera_button.clicked.connect(self.toggle_camera)
        camera_layout.addWidget(self.camera_button, stretch=1)
        
        right_panel.addLayout(camera_layout)

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
        self.resize(1100, 700)

        # State
        self.current_image_path = None
        self.current_image = None

    def populate_camera_list(self):
        """Populate the camera dropdown with available cameras."""
        self.camera_dropdown.clear()
        available_cameras = enumerate_cameras()
        
        if available_cameras:
            for cam_id, cam_name in available_cameras:
                self.camera_dropdown.addItem(cam_name, cam_id)
        else:
            self.camera_dropdown.addItem("No cameras found", -1)
            self.camera_button.setEnabled(False)

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
        self.camera_dropdown.setStyleSheet(ModernStyles.get_combobox_style())  # Apply proper ComboBox style
        self.detect_button.setStyleSheet(ModernStyles.get_button_style(is_primary=True))
        
        # Playback controls styling
        self.play_button.setStyleSheet(ModernStyles.get_button_style(is_primary=True))

        # Header
        self.findChild(QLabel, "", Qt.FindChildOption.FindDirectChildrenOnly).setStyleSheet(ModernStyles.get_label_style(is_header=True))

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
            
            # Start paused as requested? Or auto-play? 
            # User said "import videos and I wanna be able to pause them". 
            # I'll auto-play for now but provide pause.
            self.timer.start(30)
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.status_label.setText("Playing video...")
            
            # Disable manual detect button during video
            self.detect_button.setEnabled(False)

    def toggle_camera(self):
        if not self.is_camera_active:
            # Switching to camera
            self.reset_mode()
            
            # Get selected camera ID from dropdown
            selected_camera = self.camera_dropdown.currentData()
            if selected_camera is None or selected_camera < 0:
                self.status_label.setText("Error: No camera selected.")
                return
            
            self.cap = cv2.VideoCapture(selected_camera)
            if not self.cap.isOpened():
                self.status_label.setText(f"Error: Could not open camera {selected_camera}.")
                return
            
            self.timer.start(30)
            self.is_camera_active = True
            self.camera_button.setText("Stop Live Feed")
            self.load_button.setEnabled(False)
            self.load_video_button.setEnabled(False)
            self.detect_button.setEnabled(False)
            self.status_label.setText("Live feed active")
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
        self.timer.start(30)
        self.is_paused = False
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def set_position(self, position):
        if self.cap and self.is_video_file_active:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            # Update frame immediately to show seek result
            self.update_frame(single_step=True)

    def update_frame(self, single_step=False):
        if not self.cap:
            return

        ret, frame = self.cap.read()
        if ret:
            # Update slider if playing video file
            if self.is_video_file_active and not single_step:
                current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(current_frame)
                self.seek_slider.blockSignals(False)
                
                # Update time label (optional, simple frame count for now)
                self.time_label.setText(f"{current_frame} / {self.total_frames}")

            # Run detection
            try:
                result_img, detections = self.detector.detect(frame)
                active_objects, new_objects = self.tracker.update(detections)
                
                self.display_image(result_img)
                
                if new_objects:
                    self.append_results(new_objects)
                    
            except Exception as e:
                print(f"Detection error: {e}")
                self.display_image(frame)
        else:
            # End of video file
            if self.is_video_file_active:
                self.pause_video()
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Loop or stop? Stop is safer.

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
                self.results_table.setRowCount(0) # Clear for manual single image
                self.append_results(new_objects)  # Use new_objects which have IDs
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
    window = LicensePlateApp()
    window.show()
    sys.exit(app.exec())






 