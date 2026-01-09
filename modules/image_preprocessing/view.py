"""
Image Preprocessing View
Main view for the Image Preprocessing module with Camera Calibration style layout.
"""

import numpy as np
import cv2
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QGroupBox, QGridLayout, QSlider, QSpinBox,
    QCheckBox, QComboBox, QFileDialog, QScrollArea, QApplication,
    QLineEdit, QTableWidgetItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

from .widgets import RangeSlider, ProcessingDialog

try:
    from pycine.raw import read_frames as pycine_read_frames
    pycine = True
except Exception as e:
    print(f"Warning: Failed to import pycine: {e}")
    pycine = None


def imadjust_opencv(img, low_in, high_in, low_out=0, high_out=255, gamma=1.0):
    """
    img: uint8 or float image
    low_in, high_in, low_out, high_out: same scale as img
    gamma: gamma correction
    """
    # Ensure float for calculation
    img = img.astype(np.float32)

    # normalize to [0,1]
    # Handle division by zero
    diff = high_in - low_in
    if diff < 1e-5:
        diff = 1e-5
        
    img = (img - low_in) / diff
    img = np.clip(img, 0, 1)

    # gamma
    if gamma != 1.0:
        img = img ** gamma

    # scale to output range
    img = img * (high_out - low_out) + low_out
    img = np.clip(img, low_out, high_out)

    return img.astype(np.uint8)


class ZoomableImageLabel(QLabel):
    """
    Label with zoom and pan functionality for image preview.
    Simplified version for preprocessing.
    """
    
    pixelClicked = Signal(int, int, int) # x, y, intensity

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        
        # Image Data
        self._pixmap = None
        self._cv_image = None  # Store original cv2 image for processing
        
        # View State
        self._user_zoom = 1.0
        self._user_pan_x = 0.0
        self._user_pan_y = 0.0
        self.last_mouse_pos = None
        self.is_panning = False
        
    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.resetView()
        self.update()
        
    def setCvImage(self, cv_image):
        """Set image from cv2/numpy array."""
        self._cv_image = cv_image
        if cv_image is not None:
            # Convert to QPixmap
            if len(cv_image.shape) == 2:
                # Grayscale
                h, w = cv_image.shape
                bytes_per_line = w
                # Ensure data is contiguous
                if not cv_image.flags['C_CONTIGUOUS']:
                    cv_image = np.ascontiguousarray(cv_image)
                qimg = QImage(cv_image.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            else:
                # Color (BGR to RGB)
                h, w, ch = cv_image.shape
                rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
                bytes_per_line = ch * w
                if not rgb.flags['C_CONTIGUOUS']:
                    rgb = np.ascontiguousarray(rgb)
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self._pixmap = QPixmap.fromImage(qimg)
        else:
            self._pixmap = None
        self.update()
        
    def getCvImage(self):
        """Get the current cv2 image."""
        return self._cv_image
        
    def resetView(self):
        """Reset zoom and pan."""
        self._user_zoom = 1.0
        self._user_pan_x = 0.0
        self._user_pan_y = 0.0
        self.update()
        
    def _calc_transform_params(self):
        """Calculate display transform parameters."""
        if not self._pixmap or self._pixmap.isNull():
            return 1.0, 0, 0
        
        p_w = self._pixmap.width()
        p_h = self._pixmap.height()
        w_w = self.width()
        w_h = self.height()
        
        if p_w <= 0 or p_h <= 0 or w_w <= 0 or w_h <= 0:
            return 1.0, 0, 0
        
        base_scale = min(w_w / p_w, w_h / p_h)
        scale = base_scale * self._user_zoom
        
        t_w = int(p_w * scale)
        t_h = int(p_h * scale)
        
        base_x = (w_w - t_w) / 2
        base_y = (w_h - t_h) / 2
        
        t_x = int(base_x + self._user_pan_x)
        t_y = int(base_y + self._user_pan_y)
        
        return scale, t_x, t_y

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming."""
        if not self._pixmap or self._pixmap.isNull():
            return
            
        mouse_pos = event.position().toPoint()
        delta = event.angleDelta().y()
        zoom_factor = 1.15 if delta > 0 else (1.0 / 1.15)
        
        new_zoom = self._user_zoom * zoom_factor
        new_zoom = max(0.1, min(20.0, new_zoom))
        
        # Zoom towards cursor
        old_scale, old_tx, old_ty = self._calc_transform_params()
        img_x = (mouse_pos.x() - old_tx) / old_scale if old_scale > 0 else 0
        img_y = (mouse_pos.y() - old_ty) / old_scale if old_scale > 0 else 0
        
        self._user_zoom = new_zoom
        
        new_scale, new_tx, new_ty = self._calc_transform_params()
        new_widget_x = img_x * new_scale + new_tx
        new_widget_y = img_y * new_scale + new_ty
        
        self._user_pan_x += mouse_pos.x() - new_widget_x
        self._user_pan_y += mouse_pos.y() - new_widget_y
        
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.is_panning = True
            self.last_mouse_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.LeftButton:
            # Handle pixel click for intensity inspection
            if self._cv_image is not None:
                scale, tx, ty = self._calc_transform_params()
                if scale > 0:
                    pos = event.position().toPoint()
                    # Map to image coordinates
                    img_x = int((pos.x() - tx) / scale)
                    img_y = int((pos.y() - ty) / scale)
                    
                    h, w = self._cv_image.shape if len(self._cv_image.shape) == 2 else self._cv_image.shape[:2]
                    
                    if 0 <= img_x < w and 0 <= img_y < h:
                        # Get intensity
                        if len(self._cv_image.shape) == 2:
                            val = self._cv_image[img_y, img_x]
                        else:
                            # Convert to simplified intensity (grayscale equivalent) if color
                            val = int(np.mean(self._cv_image[img_y, img_x]))
                            
                        self.pixelClicked.emit(img_x, img_y, int(val))

    def mouseMoveEvent(self, event):
        if self.is_panning:
            current_pos = event.position().toPoint()
            delta = current_pos - self.last_mouse_pos
            self._user_pan_x += delta.x()
            self._user_pan_y += delta.y()
            self.last_mouse_pos = current_pos
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(13, 17, 23))  # Dark background
        
        if self._pixmap and not self._pixmap.isNull():
            scale, t_x, t_y = self._calc_transform_params()
            
            p_w = self._pixmap.width()
            p_h = self._pixmap.height()
            t_w = int(p_w * scale)
            t_h = int(p_h * scale)
            
            from PySide6.QtCore import QRect
            # Use nearest-neighbor interpolation for pixel-sharp display when zoomed
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawPixmap(QRect(t_x, t_y, t_w, t_h), self._pixmap)
        else:
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load an image to preview")


class ImagePreprocessingView(QWidget):
    """View for image preprocessing functionality with Camera Calibration style layout."""
    
    def __init__(self):
        super().__init__()
        
        # Data
        self.root_path = ""  # Main directory path
        self.camera_folders = []  # List of camera folder paths
        self.camera_images = {}  # {cam_idx: [image_paths]}
        self.camera_backgrounds = {}  # {cam_idx: background_image}
        self.cine_shifts = {}   # {abs_path: shift_bits}
        self.current_cam = 0
        self.current_frame = 0
        self.original_image = None
        self.processed_image = None
        self.current_view_mode = "original"  # original, processed, background
        self._stop_requested = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # === Title ===
        title = QLabel("Image Preprocessing")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #00d4ff; margin-bottom: 10px;")
        main_layout.addWidget(title)
        
        # === Main Content (Left: View, Right: Settings) ===
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        
        # === Left: Image Preview ===
        preview_frame = QFrame()
        preview_frame.setStyleSheet("background-color: #000000; border: 1px solid #333;")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        
        # Camera tabs (left-aligned) - FIRST
        self.cam_tabs_layout = QHBoxLayout()
        self.cam_tabs_layout.setSpacing(0)
        self.cam_tabs_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.cam_buttons = []
        # Create initial 4 camera tabs (will be updated when images loaded)
        self._create_camera_tabs(4)
        preview_layout.addLayout(self.cam_tabs_layout)
        
        # Original/Processed/Background toggle - SECOND (below camera tabs)
        toggle_layout = QHBoxLayout()
        self.original_btn = QPushButton("Original")
        self.original_btn.setCheckable(True)
        self.original_btn.setChecked(True)
        self.original_btn.setStyleSheet("""
            QPushButton { background-color: #00d4ff; color: black; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
            QPushButton:checked { background-color: #00d4ff; }
            QPushButton:!checked { background-color: #333; color: #888; }
        """)
        self.original_btn.clicked.connect(lambda: self._toggle_view("original"))
        
        self.processed_btn = QPushButton("Processed")
        self.processed_btn.setCheckable(True)
        self.processed_btn.setStyleSheet("""
            QPushButton { background-color: #333; color: #888; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
            QPushButton:checked { background-color: #00d4ff; color: black; }
            QPushButton:!checked { background-color: #333; color: #888; }
        """)
        self.processed_btn.clicked.connect(lambda: self._toggle_view("processed"))
        
        self.background_btn = QPushButton("Background")
        self.background_btn.setCheckable(True)
        self.background_btn.setStyleSheet("""
            QPushButton { background-color: #333; color: #888; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
            QPushButton:checked { background-color: #00d4ff; color: black; }
            QPushButton:!checked { background-color: #333; color: #888; }
        """)
        self.background_btn.clicked.connect(lambda: self._toggle_view("background"))
        
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.original_btn)
        toggle_layout.addWidget(self.processed_btn)
        toggle_layout.addWidget(self.background_btn)
        toggle_layout.addStretch()
        preview_layout.addLayout(toggle_layout)
        
        # Image display area (Zoomable)
        self.image_label = ZoomableImageLabel("Load an image to preview")
        self.image_label.setMinimumHeight(500)
        self.image_label.pixelClicked.connect(self._on_pixel_clicked)
        preview_layout.addWidget(self.image_label, stretch=1)
        
        content_layout.addWidget(preview_frame, stretch=2)
        
        # === Right: Settings Panel ===
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_scroll.setMinimumWidth(280)
        settings_scroll.setMaximumWidth(400)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        settings_scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; }
            QScrollBar:vertical {
                background: #1a1a2e;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #555;
            }
        """)
        
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setSpacing(12)
        settings_layout.setContentsMargins(0, 0, 10, 0)
        
        # Group box style
        group_style = """
            QGroupBox { 
                background-color: #000; 
                border: 1px solid #444; 
                font-weight: bold; 
                color: #00d4ff; 
                border-radius: 6px; 
                margin-top: 15px;
                padding-top: 15px;
            } 
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px; 
            }
        """
        
        # === Image Source ===
        source_group = QGroupBox("Image Source")
        source_group.setStyleSheet(group_style)
        source_layout = QVBoxLayout(source_group)
        
        # Num Cameras row
        from PySide6.QtWidgets import QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView
        cam_row = QHBoxLayout()
        cam_label = QLabel("Num Cameras:")
        cam_label.setStyleSheet("color: white;")
        cam_row.addWidget(cam_label)
        self.num_cameras_spin = QSpinBox()
        self.num_cameras_spin.setRange(1, 16)
        self.num_cameras_spin.setValue(4)
        self.num_cameras_spin.setStyleSheet("""
            QSpinBox { 
                background-color: #1a1a2e; 
                color: white; 
                border: 1px solid #444; 
                border-radius: 4px; 
                padding: 5px;
            }
        """)
        cam_row.addWidget(self.num_cameras_spin)
        source_layout.addLayout(cam_row)
        
        import qtawesome as qta
        
        # === Project Path (For Export) ===
        project_label = QLabel("Project Path (for Output):")
        project_label.setStyleSheet("color: white;")
        source_layout.addWidget(project_label)
        
        proj_row = QHBoxLayout()
        self.project_path_input = QLineEdit()
        self.project_path_input.setPlaceholderText("Select project output folder...")
        self.project_path_input.setStyleSheet("background-color: #1a1a2e; color: white; border: 1px solid #444; padding: 5px;")
        proj_row.addWidget(self.project_path_input)
        
        proj_browse_btn = QPushButton("")
        proj_browse_btn.setFixedWidth(40)
        proj_browse_btn.setIcon(qta.icon("fa5s.folder-open", color="white"))
        proj_browse_btn.setStyleSheet("background-color: #333; color: white; border: 1px solid #444;")
        proj_browse_btn.clicked.connect(self._browse_project_path)
        proj_row.addWidget(proj_browse_btn)
        source_layout.addLayout(proj_row)
        
        # Load Images Button
        browse_btn = QPushButton(" Load Images from Folder")
        browse_btn.setIcon(qta.icon("fa5s.images", color="black"))
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff; 
                color: black; 
                border: 1px solid #00a0cc; 
                border-radius: 4px; 
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #66e5ff; }
        """)
        browse_btn.clicked.connect(self._browse_images)
        source_layout.addWidget(browse_btn)
        
        self.image_count_label = QLabel("0 images loaded")
        self.image_count_label.setStyleSheet("color: #a0a0a0;")
        source_layout.addWidget(self.image_count_label)
        
        # Invert checkbox (applied to all image operations)
        self.invert_check = QCheckBox("Invert")
        self.invert_check.setStyleSheet("color: white;")
        self.invert_check.stateChanged.connect(self._on_settings_changed)
        source_layout.addWidget(self.invert_check)
        
        # Frame List
        frame_list_label = QLabel("Frame List (Click to Preview):")
        frame_list_label.setStyleSheet("color: white;")
        source_layout.addWidget(frame_list_label)
        
        self.frame_table = QTableWidget()
        self.frame_table.setColumnCount(2)
        self.frame_table.setHorizontalHeaderLabels(["Index", "Filename"])
        self.frame_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.frame_table.verticalHeader().setVisible(False)
        self.frame_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.frame_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.frame_table.setStyleSheet("background-color: #0d1117; border: 1px solid #333; color: white;")
        self.frame_table.setFixedHeight(120)
        self.frame_table.currentCellChanged.connect(lambda r, c, pr, pc: self._on_frame_clicked(r, c))
        source_layout.addWidget(self.frame_table)
        
        settings_layout.addWidget(source_group)
        
        # === Background Subtraction ===
        bg_group = QGroupBox("Background Subtraction")
        bg_group.setStyleSheet(group_style)
        bg_layout = QGridLayout(bg_group)
        bg_layout.setVerticalSpacing(10)
        
        self.bg_enabled = QCheckBox("Enable")
        self.bg_enabled.setStyleSheet("color: white;")
        self.bg_enabled.stateChanged.connect(self._on_settings_changed)
        bg_layout.addWidget(self.bg_enabled, 0, 0)
        
        # Calculate Background button
        self.calc_bg_btn = QPushButton("Calculate")
        self.calc_bg_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff; 
                color: black; 
                border-radius: 4px; 
                padding: 5px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #66e5ff; }
        """)
        self.calc_bg_btn.clicked.connect(self._calculate_all_backgrounds)
        bg_layout.addWidget(self.calc_bg_btn, 0, 1)
        
        # Skip Frames
        skip_label = QLabel("Skip Frames:")
        skip_label.setStyleSheet("color: white;")
        bg_layout.addWidget(skip_label, 1, 0)
        self.skip_frames_spin = QSpinBox()
        self.skip_frames_spin.setRange(0, 100)
        self.skip_frames_spin.setValue(5)
        self.skip_frames_spin.setStyleSheet("""
            QSpinBox { 
                background-color: #1a1a2e; 
                color: white; 
                border: 1px solid #444; 
                border-radius: 4px; 
                padding: 5px;
            }
        """)
        bg_layout.addWidget(self.skip_frames_spin, 1, 1)
        
        # Avg Count
        avg_label = QLabel("Avg Count:")
        avg_label.setStyleSheet("color: white;")
        bg_layout.addWidget(avg_label, 2, 0)
        self.avg_count_spin = QSpinBox()
        self.avg_count_spin.setRange(1, 999999)
        self.avg_count_spin.setValue(1000)
        self.avg_count_spin.setStyleSheet("""
            QSpinBox { 
                background-color: #1a1a2e; 
                color: white; 
                border: 1px solid #444; 
                border-radius: 4px; 
                padding: 5px;
            }
        """)
        bg_layout.addWidget(self.avg_count_spin, 2, 1)
        
        settings_layout.addWidget(bg_group)
        
        # === Image Source Info & Pixel Inspector ===
        # Place pixel info here
        self.pixel_info_label = QLabel("Click image to inspect pixel")
        self.pixel_info_label.setStyleSheet("color: #00d4ff; font-size: 11px;")
        self.pixel_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Add to top layout or somewhere visible. 
        # Putting it in main layout top bar or overlay might be complex.
        # Let's put it at the bottom of the settings scroll for now, or inside a group.
        # Actually, let's put it in the "Image Source" group for high visibility
        pass # Just initialization logic, placement happens in layout construction
        
        # ... Re-arrange layouts slightly to fit it ...
        # Let's add it to main settings layout for now
        settings_layout.addWidget(self.pixel_info_label)
        
        # === Image Adjustment ===
        adjust_group = QGroupBox("Intensity Adjustment")
        adjust_group.setStyleSheet(group_style)
        adjust_layout = QGridLayout(adjust_group)
        adjust_layout.setVerticalSpacing(12)  # 10% more spacing
        adjust_layout.setHorizontalSpacing(10)
        
        # Intensity Range Slider (Dual Handle + SpinBoxes)
        range_label = QLabel("Input Range:")
        range_label.setStyleSheet("color: white;")
        adjust_layout.addWidget(range_label, 0, 0, 1, 3)
        
        self.range_slider = RangeSlider(initial_min=0, initial_max=255)
        self.range_slider.rangeChanged.connect(self._on_settings_changed)
        adjust_layout.addWidget(self.range_slider, 1, 0, 1, 3)
        
        # Denoise (LaVision Processing)
        self.denoise_check = QCheckBox("Enhanced Denoise")
        self.denoise_check.setStyleSheet("color: white; font-weight: bold;")
        self.denoise_check.stateChanged.connect(self._on_settings_changed)
        adjust_layout.addWidget(self.denoise_check, 2, 0, 1, 3)
        
        settings_layout.addWidget(adjust_group)
        
        # === Buttons ===
        settings_layout.addStretch()
        
        preview_btn = QPushButton("Preview")
        preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff; 
                color: black; 
                border-radius: 4px; 
                padding: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #66e5ff; }
        """)
        settings_layout.addWidget(preview_btn)
        
        # Batch Process Range
        range_group = QGroupBox("Batch Process Range")
        range_group.setStyleSheet("QGroupBox { border: 1px solid #444; border-radius: 4px; margin-top: 10px; padding-top: 10px; color: #ddd; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }")
        range_layout = QHBoxLayout(range_group)
        
        range_layout.addWidget(QLabel("Start:"))
        self.batch_start_spin = QSpinBox()
        self.batch_start_spin.setRange(0, 999999)
        self.batch_start_spin.setValue(0)
        range_layout.addWidget(self.batch_start_spin)
        
        range_layout.addWidget(QLabel("End:"))
        self.batch_end_spin = QSpinBox()
        self.batch_end_spin.setRange(0, 999999)
        self.batch_end_spin.setValue(1000)
        range_layout.addWidget(self.batch_end_spin)
        
        settings_layout.addWidget(range_group)
        
        apply_btn = QPushButton("Process Image (Batch Export)")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a3f5f; 
                color: white; 
                border: 1px solid #444; 
                border-radius: 4px; 
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #3b5278; }
        """)
        apply_btn.clicked.connect(self._on_process_clicked)
        settings_layout.addWidget(apply_btn)
        
        settings_scroll.setWidget(settings_widget)
        content_layout.addWidget(settings_scroll)
        
        main_layout.addLayout(content_layout)
    
    def _create_camera_tabs(self, num_cams):
        """Create or update camera tab buttons."""
        # Clear existing buttons and stretch
        for btn in self.cam_buttons:
            self.cam_tabs_layout.removeWidget(btn)
            btn.deleteLater()
        self.cam_buttons.clear()
        
        # Remove all items from layout (including stretch)
        while self.cam_tabs_layout.count():
            item = self.cam_tabs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Create new buttons
        for i in range(num_cams):
            btn = QPushButton(f"Cam {i}")
            btn.setCheckable(True)
            btn.setChecked(i == self.current_cam)
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: #333; 
                    color: #888; 
                    border: 1px solid #444; 
                    border-radius: 4px; 
                    padding: 6px 16px; 
                    font-weight: bold; 
                    margin-right: 2px;
                }
                QPushButton:checked { 
                    background-color: #444; 
                    color: white; 
                    border-bottom: 2px solid #00d4ff;
                }
                QPushButton:hover { background-color: #3a3a3a; }
            """)
            btn.clicked.connect(lambda checked, idx=i: self._on_cam_tab_clicked(idx))
            self.cam_tabs_layout.addWidget(btn)
            self.cam_buttons.append(btn)
        
        # Add stretch at end for left alignment
        self.cam_tabs_layout.addStretch(1)
    
    def _on_cam_tab_clicked(self, cam_idx):
        """Handle click on camera tab."""
        self.current_cam = cam_idx
        # Update button states
        for i, btn in enumerate(self.cam_buttons):
            btn.setChecked(i == cam_idx)
        self._load_current_image()
    
    def _browse_images(self):
        """Open directory dialog to select main image folder."""
        import os
        
        root_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Main Image Directory",
            ""
        )
        if not root_dir:
            return
        
        self.root_path = root_dir
        # Auto-set project path to parent of root_dir if empty
        if not self.project_path_input.text():
            parent_dir = os.path.dirname(root_dir)
            self.project_path_input.setText(parent_dir)
            
        self._scan_images(root_dir)

    def _browse_project_path(self):
        """Open directory dialog to select project output folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Project Output Directory", "")
        if path:
            self.project_path_input.setText(path)

    def _scan_images(self, root_dir):
        """Scan directory for camera folders and images or cine files."""
        print(f"\n--- Scanning Directory: {root_dir} ---")
        import os
        num_cams = self.num_cameras_spin.value()
        print(f"Looking for {num_cams} cameras (settings)...")
        self.camera_images = {}
        total_images = 9999999 # Large number to find min
        self.camera_folders = []
        print(f"pycine library status: {'Available' if pycine is not None else 'NOT FOUND'}")
        
        # 1. Try Rule 2 (Flat Cine) - cine files directly in root
        root_cine_files = sorted([
            f for f in os.listdir(root_dir)
            if f.lower().endswith('.cine')
        ])
        
        if len(root_cine_files) > 0:
            print(f"Detected {len(root_cine_files)} Cine files in root: {root_cine_files}")
            # Use as many as possible up to num_cams
            actual_cams = min(len(root_cine_files), num_cams)
            for i in range(actual_cams):
                cine_path = os.path.join(root_dir, root_cine_files[i])
                if pycine:
                    try:
                        from pycine.file import read_header
                        header = read_header(cine_path)
                        cfh = header['cinefileheader']
                        n_frames = cfh.ImageCount
                        first_idx = cfh.FirstImageNo
                        # Store as virtual paths
                        self.camera_images[i] = [f"{cine_path}#{j}" for j in range(first_idx, first_idx + n_frames)]
                        total_images = min(total_images, n_frames)
                        self.camera_folders.append(cine_path)
                        print(f"Loaded Cine: {cine_path} with {n_frames} frames (Start: {first_idx})")
                    except Exception as e:
                        print(f"Error reading cine {cine_path}: {e}")
                else:
                    print("Error: pycine library not found but .cine files detected.")
            
            if len(root_cine_files) < num_cams and len(root_cine_files) > 0:
                print(f"Warning: Expected {num_cams} cameras, but found only {len(root_cine_files)} Cine files.")
            
        else:
            # 2. Try Rule 1 (Subfolders with Cine) or Standard Images
            try:
                subdirs = sorted([
                    d for d in os.listdir(root_dir) 
                    if os.path.isdir(os.path.join(root_dir, d))
                ])
            except Exception as e:
                print(f"Error scanning directory: {e}")
                return
            
            num_cams = min(num_cams, len(subdirs))
            self.camera_folders = [os.path.join(root_dir, d) for d in subdirs[:num_cams]]
            print(f"Found {len(subdirs)} subfolders. Using first {num_cams}: {subdirs[:num_cams]}")
            
            for i, folder in enumerate(self.camera_folders):
                # Check for images first
                img_files = sorted([
                    f for f in os.listdir(folder)
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'))
                ])
                
                if img_files:
                    # Standard Image Folder
                    self.camera_images[i] = [os.path.join(folder, f) for f in img_files]
                    total_images = min(total_images, len(img_files))
                else:
                    # Look for Cine (Rule 1)
                    cine_files = sorted([f for f in os.listdir(folder) if f.lower().endswith('.cine')])
                    if cine_files and pycine:
                        cine_path = os.path.join(folder, cine_files[0])
                        try:
                            from pycine.file import read_header
                            header = read_header(cine_path)
                            cfh = header['cinefileheader']
                            n_frames = cfh.ImageCount
                            first_idx = cfh.FirstImageNo
                            self.camera_images[i] = [f"{cine_path}#{j}" for j in range(first_idx, first_idx + n_frames)]
                            total_images = min(total_images, n_frames)
                            print(f"Loaded Cine from subfolder: {cine_path} with {n_frames} frames")
                        except Exception as e:
                            print(f"Error reading cine {cine_path}: {e}")
                    else:
                        self.camera_images[i] = []
                        total_images = 0

        if total_images == 9999999:
            total_images = 0
            
        # Update UI
        self.current_cam = 0
        self.current_frame = 0
        self.image_count_label.setText(f"{total_images} frames per camera")
        
        # Update batch range end to max frames
        if hasattr(self, 'batch_end_spin'):
            self.batch_end_spin.setValue(max(0, total_images - 1))
        
        # Update Camera Tabs
        self._create_camera_tabs(len(self.camera_folders))
        
        # Update Frame List
        self.frame_table.setRowCount(total_images)
        self.image_paths = [] # Keep track of frame 0 paths for table
        
        if 0 in self.camera_images:
            self.image_paths = self.camera_images[0] # Use cam 1 for list
            count = min(len(self.image_paths), total_images)
            for row in range(count):
                path = self.image_paths[row]
                if "#" in path:
                    fname = os.path.basename(path.split("#")[0]) + f" [Frame {path.split('#')[1]}]"
                else:
                    fname = os.path.basename(path)
                
                item_idx = QTableWidgetItem(str(row + 1))
                item_idx.setData(Qt.ItemDataRole.ForegroundRole, QColor("white"))
                self.frame_table.setItem(row, 0, item_idx)
                
                item_name = QTableWidgetItem(fname)
                item_name.setData(Qt.ItemDataRole.ForegroundRole, QColor("white"))
                self.frame_table.setItem(row, 1, item_name)
        
        if total_images > 0:
            self._load_current_image()
        

    
    def _populate_frame_table(self):
        """Populate the frame list table with images from first camera."""
        import os
        from PySide6.QtWidgets import QTableWidgetItem
        
        # Use first camera's images as reference
        if 0 not in self.camera_images:
            return
        
        images = self.camera_images[0]
        self.frame_table.setRowCount(len(images))
        for i, path in enumerate(images):
            idx_item = QTableWidgetItem(str(i))
            filename_item = QTableWidgetItem(os.path.basename(path))
            self.frame_table.setItem(i, 0, idx_item)
            self.frame_table.setItem(i, 1, filename_item)
        
        # Select first row
        if images:
            self.frame_table.selectRow(0)
    
    def _on_frame_clicked(self, row, col):
        """Handle click on frame table row."""
        if self.current_cam in self.camera_images:
            images = self.camera_images[self.current_cam]
            if 0 <= row < len(images):
                self.current_frame = row
                self._load_current_image()
    
    def _load_current_image(self):
        """Load the current image for preview."""
        if self.current_cam not in self.camera_images:
            return
        
        images = self.camera_images[self.current_cam]
        if not images or self.current_frame >= len(images):
            return
        
        # If we are simply viewing the background, don't read the raw image
        if self.current_view_mode == "background":
            self._toggle_view("background")
            return

        path = images[self.current_frame]
        raw_image = self._read_image(path)
        
        if raw_image is not None:
            self.original_image = raw_image  # Keep RAW (may be uint16)
            self.processed_image = None
            
            if self.current_view_mode == "processed":
                self._preview_processing()
            else:
                # For "original" view: normalize high bit-depth for display
                display_img = self._normalize_for_display(raw_image)
                if self.invert_check.isChecked():
                    display_img = 255 - display_img
                self.image_label.setCvImage(display_img)
                self._update_toggle_buttons()
    
    def _normalize_for_display(self, img):
        """Normalize high bit-depth image to 8-bit for display using percentile stretch."""
        if img.dtype == np.uint8:
            return img
        
        # Use percentile-based normalization for stable display
        p_low = np.percentile(img, 1)
        p_high = np.percentile(img, 99.5)
        
        if p_high - p_low < 1:
            p_high = p_low + 1
        
        normalized = (img.astype(np.float32) - p_low) / (p_high - p_low) * 255
        return np.clip(normalized, 0, 255).astype(np.uint8)
    
    def _toggle_view(self, view_mode):
        """Toggle between original, processed, and background view."""
        self.current_view_mode = view_mode
        self._update_toggle_buttons()
        
        if view_mode == "original":
            if self.original_image is not None:
                img = self._normalize_for_display(self.original_image)
                if self.invert_check.isChecked():
                    img = 255 - img
                self.image_label.setCvImage(img)
        elif view_mode == "processed":
            if self.processed_image is not None:
                self.image_label.setCvImage(self.processed_image)
            else:
                self._preview_processing()
        elif view_mode == "background":
            if self.current_cam in self.camera_backgrounds:
                bg = self.camera_backgrounds[self.current_cam]
                # Normalize float32 background for display
                bg_display = self._normalize_for_display(bg)
                if self.invert_check.isChecked():
                    bg_display = 255 - bg_display
                self.image_label.setCvImage(bg_display)
    
    
    def _calculate_all_backgrounds(self):
        """Calculate background for all cameras."""
        if not self.camera_images:
            return
            
        self._stop_requested = False
        
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt
        
        stride = max(1, self.skip_frames_spin.value())
        avg_count = self.avg_count_spin.value()
        num_cams = len(self.camera_images)
        
        # Calculate total frames to process for progress bar
        total_frames = 0
        for cam_idx in self.camera_images:
            images = self.camera_images[cam_idx]
            available_indices = list(range(0, len(images), stride))
            selected_count = min(len(available_indices), avg_count)
            total_frames += selected_count
        
        # Add 1 frame per camera for bit shift calculation
        total_frames += num_cams
        
        progress = QProgressDialog("Calculating backgrounds...", None, 0, total_frames, self)
        progress.setWindowTitle("Background Calculation")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setFixedSize(420, 110)
        progress.setStyleSheet("""
            QProgressDialog { background-color: #2b2b2b; color: #ffffff; padding: 15px; border: 1px solid #444; }
            QLabel { color: #ffffff; font-size: 13px; font-weight: bold; background-color: transparent; }
            QProgressBar { 
                min-height: 25px; max-height: 25px; margin: 10px 15px; 
                background-color: #444; border-radius: 4px; text-align: center; color: white;
            }
            QProgressBar::chunk { background-color: #00bcd4; border-radius: 4px; }
        """)
        progress.show()
        
        global_frame_count = 0
        
        for cam_idx in self.camera_images:
            images = self.camera_images[cam_idx]
            if not images:
                continue
            
            available_indices = list(range(0, len(images), stride))
            selected_indices = available_indices[:avg_count]
            
            
            if not selected_indices:
                continue

            accumulator = None
            count = 0
            
            # Cache 10 evenly-spaced frames for bit shift calculation
            num_samples = min(10, len(selected_indices))
            sample_step = max(1, len(selected_indices) // num_samples)
            sample_frame_indices = set(range(0, len(selected_indices), sample_step)[:num_samples])
            cached_frames = []
            
            # Helper function
            def to_gray_float32(img):
                if img is None:
                    return None
                if len(img.shape) == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                return img.astype(np.float32)
            
            # Parse cine items: (file_path, frame_idx, i, idx)
            cine_items = []
            non_cine_items = []  # (i, idx) for standard images
            for i, idx in enumerate(selected_indices):
                path = images[idx]
                if "#" in path:
                    file_path, frame_idx = path.split("#")
                    cine_items.append((file_path, int(frame_idx), i, idx))
                else:
                    non_cine_items.append((i, idx, path))
            
            # Group cine items by file_path
            from collections import defaultdict
            groups = defaultdict(list)
            for file_path, frame_idx, i, idx in cine_items:
                groups[file_path].append((frame_idx, i, idx))
            
            accumulator = None
            count = 0
            chunk_size = 100  # Smaller chunk size for better handling of sparse data
            
            # Process Cine files with chunk-based reading
            for file_path, lst in groups.items():
                if self._stop_requested:
                    break
                
                # Diagnostic: Print FirstImageNo and valid range
                # Diagnostic: Print FirstImageNo and valid range
                try:
                    from pycine.file import read_header
                    header = read_header(file_path)
                    cfh = header['cinefileheader']
                    first_no = cfh.FirstImageNo
                    img_count = cfh.ImageCount
                    last_no = first_no + img_count - 1
                except Exception as e:
                    print(f"DEBUG: Could not read metadata for {file_path}: {e}")
                    first_no, last_no = 0, 999999
                    
                lst.sort(key=lambda x: x[0])  # Sort by frame_idx
                frame_list = [x[0] for x in lst]
                want = {frame_idx: (i, idx) for frame_idx, i, idx in lst}
                
                # Warn if any requested frames are out of range
                out_of_range = [f for f in frame_list if f < first_no or f > last_no]
                if out_of_range:
                    print(f"WARNING: {len(out_of_range)} frames are out of valid range! First 5: {out_of_range[:5]}")
                
                # Read in chunks
                p = 0
                while p < len(frame_list):
                    if self._stop_requested:
                        break
                    
                    start = frame_list[p]
                    # Find end of this chunk (up to chunk_size frames or end of list)
                    q = p
                    while q + 1 < len(frame_list) and (frame_list[q + 1] - start) < chunk_size:
                        q += 1
                    end = frame_list[q]
                    
                    # Update progress every chunk
                    progress.setLabelText(f"Cam {cam_idx}: Reading frames {start}-{end}...")
                    QApplication.processEvents()
                    
                    try:
                        if not pycine:
                            break
                        # pycine: read_frames(file, start_frame, count) returns generator
                        chunk_count = end - start + 1
                        raw_images, setup, bpp = pycine_read_frames(file_path, start_frame=start, count=chunk_count)
                        imgs = list(raw_images)
                        
                        if imgs:
                            # Process frames we need from this chunk
                            for k, fr in enumerate(range(start, end + 1)):
                                if fr not in want:
                                    continue
                                
                                raw = np.array(imgs[k])
                                img = to_gray_float32(raw)
                                if img is None:
                                    continue
                                
                                if accumulator is None:
                                    accumulator = img.astype(np.float64)
                                else:
                                    accumulator += img.astype(np.float64)
                                count += 1
                                global_frame_count += 1
                                
                                i_orig, idx_orig = want[fr]
                                if i_orig in sample_frame_indices:
                                    cached_frames.append(img.copy())
                                
                                # Update progress every 20 frames
                                if count % 20 == 0:
                                    progress.setValue(global_frame_count)
                                    QApplication.processEvents()
                        
                    except Exception as e:
                        print(f"Error reading chunk {start}-{end}: {e}")
                        # Fallback: try individual frames for this chunk
                        for fr, i_orig, idx_orig in lst[p:q+1]:
                            try:
                                raw_images, _, _ = pycine_read_frames(file_path, start_frame=fr, count=1)
                                one = list(raw_images)
                                if one:
                                    raw = np.array(one[0])
                                    img = to_gray_float32(raw)
                                    if img is not None:
                                        if accumulator is None:
                                            accumulator = img.astype(np.float64)
                                        else:
                                            accumulator += img.astype(np.float64)
                                        count += 1
                                        global_frame_count += 1
                                        if i_orig in sample_frame_indices:
                                            cached_frames.append(img.copy())
                            except Exception as e2:
                                print(f"Error reading cine frame {fr}: {e2}")
                    
                    p = q + 1
            
            # Process non-cine images (standard files)
            for i, idx, path in non_cine_items:
                if self._stop_requested:
                    break
                
                img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    continue
                
                img_gray = to_gray_float32(img)
                if img_gray is None:
                    continue
                
                if accumulator is None:
                    accumulator = img_gray.astype(np.float64)
                else:
                    accumulator += img_gray.astype(np.float64)
                count += 1
                global_frame_count += 1
                
                if i in sample_frame_indices:
                    cached_frames.append(img_gray.copy())
                
                if count % 20 == 0:
                    progress.setValue(global_frame_count)
                    progress.setLabelText(f"Cam {cam_idx}: {count} frames...")
                    QApplication.processEvents()
            
            if count > 0:
                bg = (accumulator / count).astype(np.float32)
                self.camera_backgrounds[cam_idx] = bg
                
                # Calculate Bit Shift using cached frames (no re-reading!)
                progress.setLabelText(f"Cam {cam_idx}: Calculating bit shift...")
                QApplication.processEvents()
                
                subtracted_stats = []
                for raw_img in cached_frames:
                    # raw_img is now already float32 gray
                    
                    # Handle Invert logic for shift calculation
                    if self.invert_check.isChecked():
                        subtracted = np.clip(bg - raw_img, 0, None)
                    else:
                        subtracted = np.clip(raw_img - bg, 0, None)
                        
                    # Use percentile-based estimation (Robust to outliers and sparse signals)
                    subset = subtracted[::8, ::8].ravel()
                    p_val = np.percentile(subset, 99.5)
                    subtracted_stats.append(p_val)
                
                # Clear cache to free memory
                cached_frames.clear()
                
                if subtracted_stats:
                    final_p_val = np.mean(subtracted_stats)
                    if final_p_val <= 1:
                        n = 8 # Default to no shift if signal is very weak
                    else:
                        n = np.ceil(np.log2(final_p_val))
                    
                    self.cine_shifts[cam_idx] = max(0, int(n - 8))
                else:
                    self.cine_shifts[cam_idx] = 0
                
                # Advance progress for bit shift
                global_frame_count += 1
                progress.setValue(global_frame_count)
                QApplication.processEvents()
        
        progress.setValue(total_frames)
        print(f"Calculated backgrounds for {len(self.camera_backgrounds)} cameras")
    
    def _update_toggle_buttons(self):
        """Update toggle button states."""
        mode = getattr(self, 'current_view_mode', 'original')
        self.original_btn.setChecked(mode == "original")
        self.processed_btn.setChecked(mode == "processed")
        self.background_btn.setChecked(mode == "background")
    
    def _on_settings_changed(self):
        """Called when any adjustment setting changes."""
        if self.current_view_mode == "processed":
            self._preview_processing()
        else:
            # If in original or background mode, just refresh current display (handles Invert toggle)
            self._toggle_view(self.current_view_mode)
    
    
    def _apply_processing_pipeline(self, img_data, bg_data=None, cam_idx=None):
        """
        Apply the full processing pipeline to a single image.
        Pipeline: Background Subtraction (float32) -> Bit Shift (8-bit) -> Input Range -> Denoise
        """
        if cam_idx is None:
            cam_idx = self.current_cam
            
        # 0. Ensure grayscale and float32
        if len(img_data.shape) == 3:
            gray = cv2.cvtColor(img_data, cv2.COLOR_BGR2GRAY).astype(np.float32)
        else:
            gray = img_data.astype(np.float32)
        
        # 1. Background Subtraction (in float32, before bit shift)
        if self.bg_enabled.isChecked() and bg_data is not None:
            # bg_data is already float32
            # Handle Invert logic here:
            # If Invert is checked (Shadowgraphy), Signal = Background - Image
            # If Norm/Fluorescence, Signal = Image - Background
            if self.invert_check.isChecked():
                result = bg_data - gray
            else:
                result = gray - bg_data
            
            result = np.clip(result, 0, None)  # Allow values > 255 for now
        else:
            result = gray
        
        # 2. Bit Shift to 8-bit (using pre-calculated N from subtracted frame statistics)
        shift = self.cine_shifts.get(cam_idx, 0)
        
        # DEBUG Pipeline
        # p_val = np.percentile(result, 99.5)
        # Only print occasionally or for single frame preview (not batch)
        # But for now, we print always (it's fast enough for preview)
        # print(f"DEBUG Pipeline Cam {self.current_cam}: Shift={shift}, Pre-Shift Max={result.max()}, P99.5={p_val}")
        
        if shift > 0:
            result = (result / (2**shift))
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        # 3. Invert (Apply ONLY if BG subtraction was NOT done)
        # If we did (BG - Image), we already have "Bright Signal". We don't want to invert back.
        # If BG disabled, and Invert checked, we still need to invert.
        if self.invert_check.isChecked() and not (self.bg_enabled.isChecked() and bg_data is not None):
            result = 255 - result
        
        # 4. Input Range Adjustment (imadjust on 8-bit)
        low_in = self.range_slider.minValue()
        high_in = self.range_slider.maxValue()
        result = imadjust_opencv(result, low_in, high_in)
        
        # 5. LaVision Processing (Enhanced Denoise, on 8-bit)
        if self.denoise_check.isChecked():
            a = result.astype(np.float32)
            kernel = np.ones((3, 3), np.uint8)
            b = cv2.erode(a, kernel, iterations=1)
            c = a - b
            b = cv2.erode(a, kernel, iterations=1)
            c = c - b
            
            d = cv2.GaussianBlur(c, (0, 0), 0.5)
            
            k_size = 100
            e = cv2.blur(d, (k_size, k_size))
            f = a - e
            
            blurred_f = cv2.GaussianBlur(f, (0, 0), 1.0)
            sharp = f + 0.8 * (f - blurred_f)
            
            result = np.clip(sharp, 0, 255).astype(np.uint8)
        
        return result.astype(np.uint8)
    def _preview_processing(self):
        """Apply current settings and show preview."""
        if self.original_image is None:
            return
        
        # Prepare background
        bg = None
        if self.current_cam in self.camera_backgrounds:
            bg = self.camera_backgrounds[self.current_cam]
            
        # Use unified pipeline
        processed = self._apply_processing_pipeline(self.original_image, bg)
        
        self.processed_image = processed
        self._toggle_view("processed")
    def _apply_to_all(self):
        """Apply current settings to all loaded images."""
        # TODO: Implement batch processing
        print(f"Apply to all images")

    def _on_process_clicked(self):
        """Start batch processing of all images."""
        import os
        
        # Validate Project Path
        project_path = self.project_path_input.text().strip()
        if not project_path:
            # Default to parent of loaded images if empty
            if self.root_path:
                project_path = os.path.dirname(self.root_path)
            else:
                return # Should warn user
        
        if not os.path.exists(project_path):
            try:
                os.makedirs(project_path)
            except Exception as e:
                print(f"Error creating project directory: {e}")
                return

        # Prepare structure
        img_file_dir = os.path.join(project_path, "imgFile")
        if not os.path.exists(img_file_dir):
            os.makedirs(img_file_dir)
            
        # Build task list
        # List of (cam_idx, image_path, output_path)
        tasks = []
        
        # Also need to store paths for text file generation
        # cam_files_map[cam_idx] = [abs_path1, abs_path2, ...]
        cam_files_map = {} 
        
        start_idx = self.batch_start_spin.value()
        end_idx = self.batch_end_spin.value()
        
        for cam_idx, file_list in self.camera_images.items():
            cam_dir_name = f"cam{cam_idx}"
            cam_out_dir = os.path.join(img_file_dir, cam_dir_name)
            if not os.path.exists(cam_out_dir):
                os.makedirs(cam_out_dir)
            
            cam_files_map[cam_idx] = []
            
            for i, src_path in enumerate(file_list):
                if not (start_idx <= i <= end_idx):
                    continue
                    
                # Naming: img000000.tif
                filename = f"img{i:06d}.tif"
                dst_path = os.path.join(cam_out_dir, filename)
                
                # Add to task list
                tasks.append({
                    "src": src_path,
                    "dst": dst_path,
                    "cam_idx": cam_idx
                })
                
                # Record absolute path for text file
                cam_files_map[cam_idx].append(os.path.abspath(dst_path))

        if not tasks:
            return

        # Start Processing Dialog
        self.processing_dialog = ProcessingDialog(self, title="Batch Processing Images")
        self.processing_dialog.stop_signal.connect(self._stop_batch_processing)
        self.processing_dialog.pause_signal.connect(self._pause_batch_processing)
        self.processing_dialog.show()
        
        # Run processing in a separate thread/loop
        # For simplicity in this PySide implementation without separate worker class logic right here,
        # we will use QApplication.processEvents within a loop, 
        # but optimally should be QThread. 
        # Given the "agentic" constraint, let's implement a robust loop with processEvents
        # or a minimal QThread if needed. 
        # Let's use a simple generator-based approach or instant loop if fast enough, 
        # but image processing is slow.
        # Implementation: Loop with processEvents to keep UI responsive.
        
        self._is_processing = True
        self._is_paused = False
        self._stop_requested = False
        
        total = len(tasks)
        processed_count = 0
        
        for task in tasks:
            if self._stop_requested:
                break
                
            while self._is_paused:
                QApplication.processEvents()
                if self._stop_requested:
                    break
            
            # 1. Load
            src_img = self._read_image(task["src"])
            if src_img is None:
                continue
                
            # 2. Get Background
            bg = self.camera_backgrounds.get(task["cam_idx"])
            
            # 3. Process (Pipeline handles Invert internally)
            processed = self._apply_processing_pipeline(src_img, bg, cam_idx=task["cam_idx"])
            
            # 4. Save
            cv2.imwrite(task["dst"], processed)
            
            processed_count += 1
            self.processing_dialog.update_progress(processed_count, total)
            QApplication.processEvents()
        
        # Generate Text Files
        if not self._stop_requested:
            for cam_idx, paths in cam_files_map.items():
                # cam0ImageNames.txt (cam indices often 0-based in some configs, user said cam1, cam2 folders...)
                # User request: "cam1, cam2, cam3... folders" AND "cam0ImageNames.txt, cam1ImageNames.txt"
                # This explicitly implies Folder Index = 1-based, Text File Index = 0-based.
                
                txt_filename = f"cam{cam_idx}ImageNames.txt"
                txt_path = os.path.join(img_file_dir, txt_filename)
                with open(txt_path, "w") as f:
                    for p in paths:
                        f.write(p + "\n")
        
        self.processing_dialog.close()
        self._is_processing = False
        
    def _stop_batch_processing(self):
        self._stop_requested = True
        
    def _read_image(self, path):
        """Helper to read image from either file or cine frame. Returns raw data (no bit shift)."""
        import os
        if "#" in path:
            file_path, frame_idx = path.split("#")
            frame_idx = int(frame_idx)
            
            if not pycine:
                return None
            
            try:
                raw_images, setup, bpp = pycine_read_frames(file_path, start_frame=frame_idx, count=1)
                images = list(raw_images)
                if images and len(images) > 0:
                    # Return raw data (uint16 or uint8) - no bit shifting here
                    return np.array(images[0])
                else:
                    return None
            except Exception as e:
                print(f"Error reading frame {frame_idx} from {file_path}: {e}")
                return None
        else:
            return cv2.imread(path, cv2.IMREAD_UNCHANGED)

        
    def _pause_batch_processing(self, paused):
        self._is_paused = paused

    def _on_pixel_clicked(self, x, y, intensity):
        """Handle pixel click signal."""
        self.pixel_info_label.setText(f"Pixel ({x}, {y}): {intensity}")
