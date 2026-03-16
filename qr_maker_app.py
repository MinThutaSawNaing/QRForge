from __future__ import annotations

import contextlib
import os
import sys
from io import BytesIO
from pathlib import Path

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import qrcode
from PIL import Image
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

if cv2 is not None:
    with contextlib.suppress(Exception):
        if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
        elif hasattr(cv2, "setLogLevel"):
            cv2.setLogLevel(2)


WINDOW_MIN_WIDTH = 860
WINDOW_MIN_HEIGHT = 560
QR_IMAGE_SIZE = 360
BASE_DIR = Path(__file__).resolve().parent
LOGO_PNG_PATH = BASE_DIR / "logo.png"
LOGO_ICO_PATH = BASE_DIR / "logo.ico"


def create_app_icon() -> QIcon:
    if LOGO_ICO_PATH.exists():
        return QIcon(str(LOGO_ICO_PATH))
    if LOGO_PNG_PATH.exists():
        return QIcon(str(LOGO_PNG_PATH))

    pixmap = _build_demo_brand_pixmap(128)
    return QIcon(pixmap)


def create_brand_pixmap(size: int) -> QPixmap:
    if LOGO_PNG_PATH.exists():
        source = QPixmap(str(LOGO_PNG_PATH))
        if not source.isNull():
            return source.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    return _build_demo_brand_pixmap(size)


def _build_demo_brand_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rounded = QPainterPath()
    rounded.addRoundedRect(4, 4, size - 8, size - 8, size * 0.24, size * 0.24)
    painter.fillPath(rounded, QColor("#132238"))

    inner_size = size * 0.5
    inner_offset = (size - inner_size) / 2
    inner_path = QPainterPath()
    inner_path.addRoundedRect(inner_offset, inner_offset, inner_size, inner_size, 12, 12)
    painter.fillPath(inner_path, QColor("#ffffff"))

    accent_pen = QPen(QColor("#1f6f78"))
    accent_pen.setWidth(max(4, size // 18))
    painter.setPen(accent_pen)
    painter.drawLine(int(size * 0.26), int(size * 0.26), int(size * 0.26), int(size * 0.48))
    painter.drawLine(int(size * 0.26), int(size * 0.26), int(size * 0.48), int(size * 0.26))
    painter.drawLine(int(size * 0.52), int(size * 0.52), int(size * 0.74), int(size * 0.52))
    painter.drawLine(int(size * 0.74), int(size * 0.52), int(size * 0.74), int(size * 0.74))

    painter.setBrush(QColor("#1f6f78"))
    painter.setPen(Qt.PenStyle.NoPen)
    dot = max(8, size // 12)
    painter.drawRoundedRect(int(size * 0.54), int(size * 0.24), dot, dot, 4, 4)
    painter.drawRoundedRect(int(size * 0.24), int(size * 0.54), dot, dot, 4, 4)

    painter.end()
    return pixmap


class QRPreview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._pixmap: QPixmap | None = None
        self._placeholder = "Your QR code will appear here"
        self.setMinimumSize(160, 160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("qrPreview")

    def set_preview_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def clear_preview(self) -> None:
        self._pixmap = None
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        frame_rect = self.rect().adjusted(12, 12, -12, -12)
        painter.setPen(QPen(QColor("#e5edf5"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(frame_rect, 18, 18)

        inner_margin = max(18, min(frame_rect.width(), frame_rect.height()) // 12)
        target_rect = frame_rect.adjusted(inner_margin, inner_margin, -inner_margin, -inner_margin)
        side = min(target_rect.width(), target_rect.height())
        square_rect = QRect(
            target_rect.center().x() - side // 2,
            target_rect.center().y() - side // 2,
            side,
            side,
        )

        if self._pixmap is None:
            painter.setPen(QColor("#6f8299"))
            painter.drawText(square_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._placeholder)
            return

        scaled = self._pixmap.scaled(
            square_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = square_rect.x() + (square_rect.width() - scaled.width()) // 2
        y = square_rect.y() + (square_rect.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class CameraScanDialog(QDialog):
    qr_detected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cap = None
        self._timer = QTimer(self)
        self._detector = None

        self.setWindowTitle("Scan QR Code")
        self.setMinimumSize(640, 480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.video_label = QLabel("Starting camera...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setObjectName("cameraFeed")
        self.video_label.setMinimumSize(520, 320)

        self.scan_status = QLabel("Point your camera at a QR code.")
        self.scan_status.setObjectName("cameraStatus")
        self.scan_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("secondaryButton")
        self.close_button.clicked.connect(self.close)

        layout.addWidget(self.video_label, 1)
        layout.addWidget(self.scan_status)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignCenter)

        self._timer.timeout.connect(self._update_frame)

    def start_camera(self) -> bool:
        if cv2 is None:
            self.scan_status.setText("OpenCV is not installed.")
            return False

        backends = [cv2.CAP_ANY if hasattr(cv2, "CAP_ANY") else 0]
        if sys.platform == "win32":
            backends = [cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY]

        for backend in backends:
            for index in range(3):
                cap = self._try_open_camera(index, backend)
                if cap is None:
                    continue

                self._cap = cap
                self.scan_status.setText("Camera connected.")
                self._detector = cv2.QRCodeDetector()
                self._timer.start(30)
                return True

        self.scan_status.setText("Camera not available. Please check permissions.")
        return False

    def _try_open_camera(self, index: int, backend: int):
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            with contextlib.redirect_stderr(devnull):
                cap = cv2.VideoCapture(index, backend)

        if not cap or not cap.isOpened():
            if cap:
                cap.release()
            return None

        ok, _ = cap.read()
        if not ok:
            cap.release()
            return None

        return cap


    def _update_frame(self) -> None:
        if not self._cap:
            return

        ok, frame = self._cap.read()
        if not ok:
            return

        data, _, _ = self._detector.detectAndDecode(frame) if self._detector else ("", None, None)
        if data:
            self.qr_detected.emit(data)
            self.close()
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        image = QImage(rgb.data, w, h, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        if self._cap:
            self._cap.release()
            self._cap = None
        super().closeEvent(event)


class QRMakerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_image: Image.Image | None = None
        self.current_pixmap: QPixmap | None = None
        self.scan_dialog: CameraScanDialog | None = None

        self.setWindowTitle("QRForge")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self.text_input = QTextEdit()
        self.preview_label = QRPreview()
        self.status_label = QLabel("Type or paste text to generate a QR code.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("statusLabel")
        self.credit_label = QLabel("Created by Min Thuta Saw Naing")
        self.credit_label.setObjectName("creditLabel")
        self.scan_result_label = QLabel("Scanned Result")
        self.scan_result_label.setObjectName("sectionTitle")
        self.scan_result_input = QTextEdit()
        self.scan_result_input.setObjectName("scanResultInput")
        self.scan_result_input.setReadOnly(True)
        self.scan_result_input.setPlaceholderText("Camera or image scan results will appear here.")

        self.generate_button = QPushButton("Generate QR")
        self.clear_button = QPushButton("Clear")
        self.scan_button = QPushButton("Scan Camera")
        self.scan_image_button = QPushButton("Scan Image")
        self.copy_button = QPushButton("Copy QR")
        self.save_button = QPushButton("Save PNG")
        self.use_result_button = QPushButton("Use In Generator")
        self.clear_scan_result_button = QPushButton("Clear Result")
        self.create_nav_button = QPushButton("Create QR")
        self.scan_nav_button = QPushButton("Scan QR")
        self.page_stack = QStackedWidget()

        self._build_ui()
        self._wire_events()
        self._apply_styles()
        self._set_active_page(0)
        self._update_action_state()
        self.setWindowIcon(create_app_icon())

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header_card = QFrame()
        header_card.setObjectName("headerCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(14)

        logo_label = QLabel()
        logo_label.setObjectName("logoBadge")
        logo_pixmap_size = 48
        logo_label.setPixmap(create_brand_pixmap(logo_pixmap_size))
        logo_label.setFixedSize(logo_pixmap_size, logo_pixmap_size)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading_block = QWidget()
        heading_layout = QVBoxLayout(heading_block)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(2)

        title = QLabel("QRForge")
        title.setObjectName("title")
        subtitle = QLabel("Generate QR codes instantly from text, links, or Wi-Fi credentials.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")

        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)

        header_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(heading_block, 1, Qt.AlignmentFlag.AlignVCenter)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        nav_card = QFrame()
        nav_card.setObjectName("navCard")
        nav_card.setFixedWidth(200)
        nav_layout = QVBoxLayout(nav_card)
        nav_layout.setContentsMargins(14, 14, 14, 14)
        nav_layout.setSpacing(10)

        nav_title = QLabel("Workspace")
        nav_title.setObjectName("navTitle")
        nav_hint = QLabel("Switch between creation and scanning.")
        nav_hint.setObjectName("navHint")
        nav_hint.setWordWrap(True)

        self.create_nav_button.setObjectName("navButton")
        self.scan_nav_button.setObjectName("navButton")
        self.create_nav_button.setCheckable(True)
        self.scan_nav_button.setCheckable(True)

        nav_layout.addWidget(nav_title)
        nav_layout.addWidget(nav_hint)
        nav_layout.addSpacing(6)
        nav_layout.addWidget(self.create_nav_button)
        nav_layout.addWidget(self.scan_nav_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.credit_label)

        self.page_stack.addWidget(self._build_create_page())
        self.page_stack.addWidget(self._build_scan_page())

        content_layout.addWidget(nav_card)
        content_layout.addWidget(self.page_stack, 1)

        root_layout.addWidget(header_card)
        root_layout.addLayout(content_layout, 1)

    def _build_create_page(self) -> QWidget:
        page = QWidget()
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)

        # --- Editor panel (scrollable) ---
        editor_card = QFrame()
        editor_card.setObjectName("panel")
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(18, 18, 18, 18)
        editor_layout.setSpacing(10)

        editor_title = QLabel("Create From Text")
        editor_title.setObjectName("sectionTitle")
        editor_subtitle = QLabel("Paste a link, note, Wi-Fi payload, or anything else you want to turn into a QR code.")
        editor_subtitle.setObjectName("sectionBody")
        editor_subtitle.setWordWrap(True)

        self.text_input.setPlaceholderText(
            "Paste a URL, message, Wi-Fi payload, product ID, or any text you want to encode..."
        )
        self.text_input.setAcceptRichText(False)
        self.text_input.setObjectName("textInput")
        self.text_input.setMinimumHeight(100)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)
        button_row.setSpacing(10)
        self.generate_button.setObjectName("primaryButton")
        self.clear_button.setObjectName("secondaryButton")
        self.generate_button.setMinimumWidth(130)
        self.clear_button.setMinimumWidth(100)
        button_row.addStretch(1)
        button_row.addWidget(self.generate_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)

        editor_layout.addWidget(editor_title)
        editor_layout.addWidget(editor_subtitle)
        editor_layout.addWidget(self.text_input, 1)
        editor_layout.addLayout(button_row)
        editor_layout.addWidget(self.status_label)

        # --- Preview panel ---
        preview_card = QFrame()
        preview_card.setObjectName("panel")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        preview_layout.setSpacing(10)

        preview_title = QLabel("Preview And Export")
        preview_title.setObjectName("sectionTitle")
        preview_subtitle = QLabel("Review the QR code, then copy or save as PNG.")
        preview_subtitle.setObjectName("sectionBody")
        preview_subtitle.setWordWrap(True)

        preview_actions = QHBoxLayout()
        preview_actions.setContentsMargins(0, 6, 0, 0)
        preview_actions.setSpacing(10)
        self.copy_button.setObjectName("secondaryButton")
        self.save_button.setObjectName("primaryButton")
        self.copy_button.setMinimumWidth(110)
        self.save_button.setMinimumWidth(110)
        preview_actions.addStretch(1)
        preview_actions.addWidget(self.copy_button)
        preview_actions.addWidget(self.save_button)
        preview_actions.addStretch(1)

        preview_canvas = QFrame()
        preview_canvas.setObjectName("previewCanvas")
        preview_canvas_layout = QVBoxLayout(preview_canvas)
        preview_canvas_layout.setContentsMargins(10, 10, 10, 10)
        preview_canvas_layout.setSpacing(8)

        preview_meta = QLabel("Live Preview")
        preview_meta.setObjectName("previewMeta")

        preview_canvas_layout.addWidget(preview_meta)
        preview_canvas_layout.addWidget(self.preview_label, 1)

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_subtitle)
        preview_layout.addWidget(preview_canvas, 1)
        preview_layout.addLayout(preview_actions)

        page_layout.addWidget(editor_card, 5)
        page_layout.addWidget(preview_card, 5)
        return page

    def _build_scan_page(self) -> QWidget:
        page = QWidget()
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)

        scan_actions_card = QFrame()
        scan_actions_card.setObjectName("panel")
        scan_actions_layout = QVBoxLayout(scan_actions_card)
        scan_actions_layout.setContentsMargins(18, 18, 18, 18)
        scan_actions_layout.setSpacing(10)

        scan_title = QLabel("Scan QR Codes")
        scan_title.setObjectName("sectionTitle")
        scan_body = QLabel("Use your default camera or upload an image file to read existing QR codes quickly.")
        scan_body.setObjectName("sectionBody")
        scan_body.setWordWrap(True)

        scan_button_row = QHBoxLayout()
        scan_button_row.setSpacing(10)
        self.scan_button.setObjectName("primaryButton")
        self.scan_image_button.setObjectName("secondaryButton")
        scan_button_row.addWidget(self.scan_button)
        scan_button_row.addWidget(self.scan_image_button)

        scan_tip = QLabel("Tip: If your webcam is blocked by another app, image upload is usually the fastest fallback.")
        scan_tip.setObjectName("infoLabel")
        scan_tip.setWordWrap(True)

        scan_actions_layout.addWidget(scan_title)
        scan_actions_layout.addWidget(scan_body)
        scan_actions_layout.addLayout(scan_button_row)
        scan_actions_layout.addWidget(scan_tip)
        scan_actions_layout.addStretch(1)

        result_card = QFrame()
        result_card.setObjectName("panel")
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(18, 18, 18, 18)
        result_layout.setSpacing(10)

        self.scan_result_input.setMinimumHeight(80)

        result_actions = QHBoxLayout()
        result_actions.setSpacing(10)
        self.use_result_button.setObjectName("primaryButton")
        self.clear_scan_result_button.setObjectName("secondaryButton")
        result_actions.addWidget(self.use_result_button)
        result_actions.addWidget(self.clear_scan_result_button)

        result_layout.addWidget(self.scan_result_label)
        result_layout.addWidget(self.scan_result_input, 1)
        result_layout.addLayout(result_actions)

        page_layout.addWidget(scan_actions_card, 4)
        page_layout.addWidget(result_card, 6)
        return page

    def _wire_events(self) -> None:
        self.generate_button.clicked.connect(self.generate_qr_code)
        self.clear_button.clicked.connect(self.clear_all)
        self.scan_button.clicked.connect(self.open_scan_dialog)
        self.scan_image_button.clicked.connect(self.scan_qr_from_image)
        self.copy_button.clicked.connect(self.copy_image)
        self.save_button.clicked.connect(self.save_image)
        self.use_result_button.clicked.connect(self.use_scanned_result)
        self.clear_scan_result_button.clicked.connect(self.clear_scanned_result)
        self.create_nav_button.clicked.connect(lambda: self._set_active_page(0))
        self.scan_nav_button.clicked.connect(lambda: self._set_active_page(1))
        self.text_input.textChanged.connect(self._handle_text_changed)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4f7fb;
            }
            QFrame#headerCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #132238,
                    stop: 1 #1f6f78
                );
                border-radius: 16px;
            }
            QFrame#panel {
                background: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 16px;
            }
            QFrame#navCard {
                background: #132238;
                border: 1px solid #1e395a;
                border-radius: 16px;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#logoBadge {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                padding: 6px;
            }
            QLabel#subtitle {
                color: #dce7ef;
                font-size: 13px;
            }
            QLabel#navTitle {
                color: #ffffff;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#navHint {
                color: #b9c7d6;
                font-size: 12px;
            }
            QLabel#sectionTitle {
                color: #132238;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#sectionBody {
                color: #62758a;
                font-size: 13px;
            }
            QLabel#statusLabel {
                min-height: 28px;
                padding-top: 2px;
                color: #5d7086;
                font-size: 13px;
            }
            QLabel#creditLabel {
                color: #d7e2ee;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#infoLabel {
                color: #5d7086;
                font-size: 12px;
                font-weight: 600;
            }
            QFrame#previewCanvas {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #eef4fb,
                    stop: 1 #f9fbfe
                );
                border: 1px solid #d6e0ea;
                border-radius: 14px;
            }
            QLabel#previewMeta {
                color: #5b6c80;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            QLabel#qrPreview {
                background: transparent;
                border: none;
                padding: 0;
            }
            QTextEdit#textInput {
                background: #fbfdff;
                border: 1px solid #d9e2ec;
                border-radius: 12px;
                color: #132238;
                font-size: 14px;
                padding: 10px;
                selection-background-color: #c6eef0;
            }
            QTextEdit#textInput:focus {
                border: 1px solid #1f6f78;
            }
            QTextEdit#scanResultInput {
                background: #fbfdff;
                border: 1px solid #d9e2ec;
                border-radius: 12px;
                color: #132238;
                font-size: 14px;
                padding: 10px;
            }
            QLabel#cameraFeed {
                background: #0f1724;
                border: 1px solid #1e293b;
                border-radius: 12px;
                color: #d9e2ec;
                font-size: 14px;
            }
            QLabel#cameraStatus {
                color: #5d7086;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel {
                color: #4f5f73;
            }
            QPushButton {
                min-height: 38px;
                padding: 0 16px;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
                text-align: center;
            }
            QPushButton#primaryButton {
                background: #132238;
                color: #ffffff;
                border: none;
            }
            QPushButton#primaryButton:hover {
                background: #1a304c;
            }
            QPushButton#secondaryButton {
                background: #edf3f8;
                color: #132238;
                border: 1px solid #d1dde8;
            }
            QPushButton#secondaryButton:hover {
                background: #e5eef6;
            }
            QPushButton#navButton {
                min-height: 42px;
                background: rgba(255, 255, 255, 0.06);
                color: #eff6fb;
                border: 1px solid rgba(255, 255, 255, 0.12);
                text-align: left;
                padding-left: 14px;
            }
            QPushButton#navButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
            QPushButton#navButton:checked {
                background: #f3f8fc;
                color: #132238;
                border: 1px solid #dce8f2;
            }
            QPushButton:disabled {
                background: #dfe7ef;
                color: #8b99aa;
                border: none;
            }
            """
        )

    def _handle_text_changed(self) -> None:
        text = self.text_input.toPlainText().strip()
        if text:
            self.generate_qr_code()
        else:
            self._reset_preview()

    def _reset_preview(self) -> None:
        self.current_image = None
        self.current_pixmap = None
        self.preview_label.clear_preview()
        self.status_label.setText("Type or paste text to generate a QR code.")
        self._update_action_state()

    def _update_action_state(self) -> None:
        has_text = bool(self.text_input.toPlainText().strip())
        has_image = self.current_pixmap is not None
        has_scan_result = bool(self.scan_result_input.toPlainText().strip())
        self.generate_button.setEnabled(has_text)
        self.clear_button.setEnabled(has_text or has_image)
        self.scan_button.setEnabled(True)
        self.scan_image_button.setEnabled(cv2 is not None)
        self.copy_button.setEnabled(has_image)
        self.save_button.setEnabled(has_image)
        self.use_result_button.setEnabled(has_scan_result)
        self.clear_scan_result_button.setEnabled(has_scan_result)

    def generate_qr_code(self) -> None:
        text = self.text_input.toPlainText().strip()
        if not text:
            self._reset_preview()
            return

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)

        self.current_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        self.current_pixmap = self._pil_image_to_pixmap(self.current_image)

        self._refresh_preview()
        self.status_label.setText(f"QR code ready for {len(text)} character(s).")
        self._update_action_state()

    def copy_image(self) -> None:
        if not self.current_pixmap:
            return

        clipboard = QGuiApplication.clipboard()
        clipboard.setPixmap(self.current_pixmap)
        self.status_label.setText("QR code copied to clipboard.")

    def save_image(self) -> None:
        if not self.current_image:
            return

        default_path = Path.home() / "qr-code.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save QR Code",
            str(default_path),
            "PNG Files (*.png)",
        )
        if not file_path:
            return

        save_path = Path(file_path)
        if save_path.suffix.lower() != ".png":
            save_path = save_path.with_suffix(".png")

        try:
            self.current_image.save(save_path, format="PNG")
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not save the QR image.\n\n{exc}")
            return

        self.status_label.setText(f"Saved QR code to {save_path}.")

    def clear_all(self) -> None:
        self.text_input.clear()
        self._reset_preview()

    def open_scan_dialog(self) -> None:
        if cv2 is None:
            QMessageBox.warning(
                self,
                "Scanner Unavailable",
                "QR scanning needs OpenCV. Install it with:\n\npip install opencv-python",
            )
            return

        allow = QMessageBox.question(
            self,
            "Camera Permission",
            "QRForge would like to use your camera to scan a QR code.\n\nAllow camera access?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if allow != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Camera access denied.")
            return

        self.scan_dialog = CameraScanDialog(self)
        self.scan_dialog.qr_detected.connect(self._handle_scanned_qr)
        if not self.scan_dialog.start_camera():
            QMessageBox.warning(
                self,
                "Camera Error",
                "QRForge could not access a usable camera.\n\n"
                "Please check Windows Camera privacy settings, close apps using the camera, "
                "or use Scan Image instead.",
            )
            self.scan_dialog.close()
            self.scan_dialog = None
            return
        self.scan_dialog.show()

    def scan_qr_from_image(self) -> None:
        if cv2 is None:
            QMessageBox.warning(
                self,
                "Scanner Unavailable",
                "QR scanning needs OpenCV. Install it with:\n\npip install opencv-python",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image to Scan",
            str(Path.home()),
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not file_path:
            return

        image = cv2.imread(file_path)
        if image is None:
            QMessageBox.warning(self, "Open Failed", "The selected image could not be read.")
            return

        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(image)
        if not data:
            QMessageBox.information(self, "No QR Found", "No QR code was detected in that image.")
            self.status_label.setText("No QR code found in the selected image.")
            return

        self._handle_scanned_qr(data, source_name=Path(file_path).name)

    def _handle_scanned_qr(self, data: str, source_name: str = "camera") -> None:
        if not data:
            return
        self.scan_result_input.setPlainText(data)
        self.status_label.setText(f"QR code scanned from {source_name}.")
        self._set_active_page(1)
        self._update_action_state()

    def use_scanned_result(self) -> None:
        scanned_text = self.scan_result_input.toPlainText().strip()
        if not scanned_text:
            return

        self.text_input.setPlainText(scanned_text)
        self.generate_qr_code()
        self._set_active_page(0)
        self.status_label.setText("Scanned content loaded into the generator.")

    def clear_scanned_result(self) -> None:
        self.scan_result_input.clear()
        self._update_action_state()

    def _set_active_page(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index)
        self.create_nav_button.setChecked(index == 0)
        self.scan_nav_button.setChecked(index == 1)

    def _refresh_preview(self) -> None:
        if not self.current_pixmap:
            return
        self.preview_label.set_preview_pixmap(self.current_pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.current_pixmap:
            self.preview_label.update()

    @staticmethod
    def _pil_image_to_pixmap(image: Image.Image) -> QPixmap:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        qimage = QImage.fromData(buffer.getvalue(), "PNG")
        return QPixmap.fromImage(qimage)
