import argparse
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from app import run_lfs_densification_stage
from scripts.dependency_checks import locate_colmap, resolve_executable
from xpano_workbench import __version__
from scripts.runtime_paths import locate_ffprobe
from xpano_workbench.media_import import (
    PANORAMA_EXTENSIONS,
    VIDEO_EXTENSIONS,
    estimate_photo_selection,
    estimate_video_frame_count,
    is_photo_path,
    iter_valid_photo_folder,
    probe_video_duration,
)
from xpano_workbench.models import (
    AERIAL_PHOTOS,
    ORDINARY_VIDEO,
    PANORAMA_VIDEO,
    STANDARD_PHOTOS,
    ExtractionSettings,
    WorkbenchTrack,
    create_track,
)
from xpano_workbench.reconstruction_scene import CameraPose, ColoredPoint, ReconstructionScene, load_reconstruction_scene, resolve_colmap_scene_root
from xpano_workbench.runner import WorkbenchEventSink, WorkbenchRunConfig, run_workbench_pipeline


try:
    from PySide6.QtCore import Property, QEasingCurve, QObject, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, QUrl, Signal, QSize
    from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap, QPolygonF
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QStatusBar,
        QTextEdit,
        QToolButton,
        QVBoxLayout,
        QWidget,
        QDoubleSpinBox,
        QSpinBox,
    )
except ImportError as exc:  # pragma: no cover - covered by release/runtime smoke tests.
    raise SystemExit(
        "PySide6 is required for xPano Workbench. "
        "Install requirements.txt or run the portable release build."
    ) from exc


try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - optional viewer backend.
    QWebEngineView = None


ICON_STROKES = {
    "pano": [(7, 18, 15, 10), (15, 10, 25, 18), (25, 18, 17, 26), (17, 26, 7, 18)],
    "video": [(7, 10, 23, 10), (23, 10, 23, 24), (23, 24, 7, 24), (7, 24, 7, 10), (23, 15, 29, 12), (29, 12, 29, 22), (29, 22, 23, 19)],
    "folder": [(6, 12, 14, 12), (14, 12, 17, 15), (17, 15, 30, 15), (30, 15, 30, 26), (30, 26, 6, 26), (6, 26, 6, 12)],
    "run": [(11, 8, 25, 17), (25, 17, 11, 26), (11, 26, 11, 8)],
    "stop": [(10, 10, 26, 10), (26, 10, 26, 26), (26, 26, 10, 26), (10, 26, 10, 10)],
    "output": [(10, 8, 26, 8), (26, 8, 26, 26), (26, 26, 10, 26), (10, 26, 10, 8), (14, 18, 22, 18), (22, 18, 18, 22), (22, 18, 18, 14)],
    "env": [(18, 8, 18, 14), (18, 22, 18, 28), (8, 18, 14, 18), (22, 18, 28, 18), (13, 13, 23, 23), (23, 13, 13, 23)],
}

ICON_FILES = {
    "pano": "camera.svg",
    "camera": "camera.svg",
    "video": "video.svg",
    "folder": "folder-open.svg",
    "photos": "images.svg",
    "plus": "plus.svg",
    "run": "play.svg",
    "stop": "circle-stop.svg",
    "output": "folder-open.svg",
    "env": "settings.svg",
    "settings": "settings.svg",
    "loader": "loader-circle.svg",
    "close": "x.svg",
}


def _icon_dir():
    return Path(__file__).resolve().parent / "assets" / "icons"


def make_icon(name, color="#273449"):
    icon_file = ICON_FILES.get(name)
    if icon_file:
        path = _icon_dir() / icon_file
        if path.exists():
            return QIcon(str(path))
    pixmap = QPixmap(36, 36)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 2.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for x1, y1, x2, y2 in ICON_STROKES.get(name, []):
        painter.drawLine(x1, y1, x2, y2)
    painter.end()
    return QIcon(pixmap)


def install_application_font(app):
    preferred = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Segoe UI", "Arial", "DejaVu Sans"]
    families = QFontDatabase.families()
    if any(name in families for name in preferred[:3]):
        family = next((name for name in preferred if name in families), families[0])
        app.setFont(QFont(family, 10))
        return
    font_files = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for font_file in font_files:
        if not font_file.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            app.setFont(QFont(families[0] if families else preferred[1], 10))
            return
    app.setFont(QFont(preferred[1], 10))


def make_demo_fisheye(label, accent):
    pixmap = QPixmap(900, 620)
    pixmap.fill(QColor("#090f1b"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    center_x = pixmap.width() / 2
    center_y = pixmap.height() / 2
    radius = min(pixmap.width(), pixmap.height()) * 0.42
    painter.setBrush(QColor("#101827"))
    painter.setPen(QPen(QColor("#253047"), 5))
    painter.drawEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))
    for index in range(12):
        angle = index * math.pi / 6
        inner = radius * 0.16
        outer = radius * 0.92
        painter.setPen(QPen(QColor(accent), 1.2 if index % 3 else 2.2))
        painter.drawLine(
            center_x + math.cos(angle) * inner,
            center_y + math.sin(angle) * inner,
            center_x + math.cos(angle) * outer,
            center_y + math.sin(angle) * outer,
        )
    for radius_scale in [0.28, 0.46, 0.64, 0.82]:
        painter.setPen(QPen(QColor("#30405f"), 1))
        ring = radius * radius_scale
        painter.drawEllipse(QRectF(center_x - ring, center_y - ring, ring * 2, ring * 2))
    painter.setPen(QColor("#f8fafc"))
    painter.setFont(QApplication.font())
    painter.drawText(QRectF(24, 22, 300, 36), Qt.AlignLeft | Qt.AlignVCenter, label)
    painter.end()
    return pixmap


def make_demo_reconstruction_scene():
    random.seed(7)
    sparse = []
    dense = []
    for index in range(900):
        theta = index * 0.19
        radius = 0.7 + random.random() * 1.5
        xyz = (
            math.cos(theta) * radius,
            math.sin(theta * 0.73) * 0.7,
            math.sin(theta) * radius * 0.65,
        )
        rgb = (
            int(110 + 80 * random.random()),
            int(150 + 70 * random.random()),
            int(180 + 60 * random.random()),
        )
        sparse.append(ColoredPoint(xyz=xyz, rgb=rgb))
    for index in range(6000):
        theta = index * 0.071
        radius = 0.55 + random.random() * 1.8
        xyz = (
            math.cos(theta) * radius + random.uniform(-0.03, 0.03),
            math.sin(theta * 0.77) * 0.78 + random.uniform(-0.03, 0.03),
            math.sin(theta) * radius * 0.68 + random.uniform(-0.03, 0.03),
        )
        rgb = (
            int(80 + 120 * random.random()),
            int(120 + 105 * random.random()),
            int(130 + 100 * random.random()),
        )
        dense.append(ColoredPoint(xyz=xyz, rgb=rgb))
    cameras = []
    for index in range(16):
        angle = index / 15 * math.pi * 1.35
        cameras.append(
            CameraPose(
                name=f"camera_{index:03d}.jpg",
                position=(math.cos(angle) * 2.2, math.sin(index * 0.31) * 0.42, math.sin(angle) * 1.45),
                wxyz=(1.0, 0.0, 0.0, 0.0),
                fov=0.9,
                aspect=1.5,
            )
        )
    return ReconstructionScene(
        sparse_points=tuple(sparse),
        dense_points=tuple(dense),
        cameras=tuple(cameras),
    )


class TrackListItem(QListWidgetItem):
    def __init__(self, track: WorkbenchTrack):
        super().__init__("")
        self.track_id = track.track_id


class SectionTitle(QWidget):
    def __init__(self, text):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 6)
        layout.setSpacing(10)
        label = QLabel(text.upper())
        label.setObjectName("SectionTitle")
        line = QFrame()
        line.setObjectName("SectionLine")
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(label)
        layout.addWidget(line, 1)


class CollapsibleSection(QWidget):
    def __init__(self, title, expanded=False):
        super().__init__()
        self._expanded = bool(expanded)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.toggle_button = QToolButton()
        self.toggle_button.setObjectName("CollapseHeader")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(self._expanded)
        self.toggle_button.clicked.connect(self.set_expanded)
        layout.addWidget(self.toggle_button)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)
        layout.addWidget(self.body)
        self.set_expanded(self._expanded)

    def addWidget(self, widget):
        self.body_layout.addWidget(widget)

    def set_expanded(self, expanded):
        self._expanded = bool(expanded)
        self.toggle_button.setChecked(self._expanded)
        self.toggle_button.setIcon(make_icon("loader" if self._expanded else "plus"))
        self.body.setVisible(self._expanded)


class BackendSwitch(QWidget):
    changed = Signal(str)

    def __init__(self, value="metashape", parent=None):
        super().__init__(parent)
        self._value = None
        self._slider_position = 0.0
        self.setObjectName("BackendSwitch")
        self.setMinimumHeight(38)
        self.animation = QPropertyAnimation(self, b"sliderPosition", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        self.metashape_button = QPushButton("Metashape")
        self.metashape_button.setObjectName("BackendOption")
        self.colmap_button = QPushButton("COLMAP")
        self.colmap_button.setObjectName("BackendOption")
        self.metashape_button.clicked.connect(lambda: self.set_backend("metashape"))
        self.colmap_button.clicked.connect(lambda: self.set_backend("colmap"))
        layout.addWidget(self.metashape_button)
        layout.addWidget(self.colmap_button)
        self.set_backend(value, emit=False)

    def currentText(self):
        return self._value

    def get_slider_position(self):
        return self._slider_position

    def set_slider_position(self, value):
        self._slider_position = max(0.0, min(1.0, float(value)))
        self.update()

    sliderPosition = Property(float, get_slider_position, set_slider_position)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        margin = 3.0
        width = max(0.0, (self.width() - margin * 2) / 2.0)
        height = max(0.0, self.height() - margin * 2)
        rect = QRectF(margin + width * self._slider_position, margin, width, height)
        painter.setBrush(QColor("#dbeafe"))
        painter.setPen(QPen(QColor("#2563eb"), 1.4))
        painter.drawRoundedRect(rect, 8, 8)
        painter.end()

    def setCurrentText(self, value):
        self.set_backend(value)

    def set_backend(self, value, emit=True):
        value = "colmap" if str(value).lower() == "colmap" else "metashape"
        if value == self._value:
            return
        self._value = value
        self.metashape_button.setProperty("selected", value == "metashape")
        self.colmap_button.setProperty("selected", value == "colmap")
        self.setProperty("backend", value)
        for button in [self.metashape_button, self.colmap_button, self]:
            button.style().unpolish(button)
            button.style().polish(button)
        self._move_slider(animated=emit)
        if emit:
            self.changed.emit(value)

    def _move_slider(self, animated=True):
        target = 1.0 if self._value == "colmap" else 0.0
        if animated:
            self.animation.stop()
            self.animation.setStartValue(self._slider_position)
            self.animation.setEndValue(target)
            self.animation.start()
        else:
            self.set_slider_position(target)


def track_icon_name(track_type):
    return {
        PANORAMA_VIDEO: "pano",
        ORDINARY_VIDEO: "video",
        STANDARD_PHOTOS: "folder",
        AERIAL_PHOTOS: "folder",
    }.get(track_type, "folder")


def track_type_title(track_type):
    return {
        PANORAMA_VIDEO: "全景",
        ORDINARY_VIDEO: "视频",
        STANDARD_PHOTOS: "照片",
        AERIAL_PHOTOS: "照片",
    }.get(track_type, track_type)


def photo_paths_from_material(paths):
    photos = []
    for item in paths:
        path = Path(item)
        if path.is_dir():
            photos.extend(iter_valid_photo_folder(path))
        elif path.is_file() and is_photo_path(path):
            photos.append(path.resolve())
        else:
            raise ValueError(f"照片素材只能包含照片文件或照片文件夹：{path}")
    return sorted(dict.fromkeys(photos))


class MarqueeLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(280)
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self._offset = 0
        self.setToolTip(self._full_text)
        self._refresh()

    def _tick(self):
        if len(self._full_text) <= 32:
            return
        self._offset = (self._offset + 1) % (len(self._full_text) + 5)
        self._refresh()

    def _refresh(self):
        if len(self._full_text) <= 32:
            super().setText(self._full_text)
            return
        source = f"{self._full_text}     {self._full_text}"
        super().setText(source[self._offset:self._offset + 32])


class MaterialTypeDialog(QDialog):
    OPTIONS = (
        (PANORAMA_VIDEO, "全景", "pano"),
        (ORDINARY_VIDEO, "视频", "video"),
        (STANDARD_PHOTOS, "照片", "folder"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_type = PANORAMA_VIDEO
        self.setWindowTitle("选择素材类型")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        title = QLabel("选择素材类型")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.buttons = []
        for index, (track_type, label, icon_name) in enumerate(self.OPTIONS):
            button = QToolButton()
            button.setObjectName("TypeCard")
            button.setCheckable(True)
            button.setIcon(make_icon(icon_name))
            button.setIconSize(QSize(30, 30))
            button.setText(label)
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.clicked.connect(lambda _checked=False, value=track_type: self._select(value))
            grid.addWidget(button, 0, index)
            self.buttons.append((track_type, button))
        layout.addLayout(grid)
        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        self.next_button = QPushButton("下一步")
        self.next_button.setObjectName("PrimaryButton")
        self.next_button.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(self.next_button)
        layout.addLayout(actions)
        self._select(self.selected_type)

    def _select(self, track_type):
        self.selected_type = track_type
        for value, button in self.buttons:
            button.setChecked(value == track_type)


class DurationProbeSignals(QObject):
    loaded = Signal(object)


class TrackSettingsDialog(QDialog):
    def __init__(self, track_type, paths, extraction=None, photo_limit=0, media_duration_seconds=None, parent=None):
        super().__init__(parent)
        self.track_type = track_type
        self.paths = tuple(Path(path) for path in paths)
        self._photo_total = 0
        self._duration = media_duration_seconds
        self._duration_signals = DurationProbeSignals()
        self._duration_signals.loaded.connect(self._on_duration_loaded)
        self.setWindowTitle("素材轨设置")
        self.setModal(True)
        self.extraction = extraction or ExtractionSettings()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        title = QLabel(f"{track_type_title(track_type)}素材轨设置")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        self.estimate_label = QLabel("")
        self.estimate_label.setObjectName("MutedLabel")
        layout.addWidget(self.estimate_label)
        self.loading_bar = QProgressBar()
        self.loading_bar.setObjectName("InlineLoading")
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        if track_type in {PANORAMA_VIDEO, ORDINARY_VIDEO}:
            self._build_video_form(form)
        else:
            self._build_photo_form(form, photo_limit)
        layout.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("确定")
        ok.setObjectName("PrimaryButton")
        ok.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(ok)
        layout.addLayout(actions)
        self._update_estimate()

    def _build_video_form(self, form):
        if self._duration is None:
            self.loading_bar.show()
            self.estimate_label.setText("正在加载素材")
            threading.Thread(target=self._probe_duration_worker, daemon=True).start()
        self.spf = QDoubleSpinBox()
        self.spf.setRange(0.01, 9999.0)
        self.spf.setDecimals(2)
        self.spf.setSingleStep(0.25)
        self.spf.setValue(self.extraction.seconds_per_frame)
        self.spf.valueChanged.connect(self._update_estimate)
        form.addRow("秒/帧", self.spf)

        self.start_time = QDoubleSpinBox()
        self.start_time.setRange(0.0, 1_000_000.0)
        self.start_time.setDecimals(2)
        self.start_time.setSuffix(" s")
        self.start_time.setValue(self.extraction.start_time_seconds)
        self.start_time.valueChanged.connect(self._update_estimate)
        form.addRow("开始", self.start_time)

        self.end_time = QDoubleSpinBox()
        self.end_time.setRange(0.0, 1_000_000.0)
        self.end_time.setDecimals(2)
        self.end_time.setSuffix(" s")
        self.end_time.setSpecialValueText("到结尾")
        self.end_time.setValue(self.extraction.end_time_seconds)
        self.end_time.valueChanged.connect(self._update_estimate)
        form.addRow("结束", self.end_time)

        self.max_frames = QSpinBox()
        self.max_frames.setRange(0, 1_000_000)
        self.max_frames.setSpecialValueText("全部")
        self.max_frames.setValue(self.extraction.max_frames)
        self.max_frames.valueChanged.connect(self._update_estimate)
        form.addRow("最大帧数", self.max_frames)

    def _probe_duration_worker(self):
        duration = probe_video_duration(self.paths[0], locate_ffprobe())
        self._duration_signals.loaded.emit(duration)

    def _on_duration_loaded(self, duration):
        self._duration = duration
        self.loading_bar.hide()
        self._update_estimate()

    def _build_photo_form(self, form, photo_limit):
        self._photo_total = len(photo_paths_from_material(self.paths))
        selected, total = estimate_photo_selection(self._photo_total, photo_limit)
        self.max_photos = QSpinBox()
        self.max_photos.setRange(min(10, total), total)
        self.max_photos.setValue(selected)
        self.max_photos.valueChanged.connect(self._update_estimate)
        form.addRow("最大张数", self.max_photos)

    def _video_settings(self):
        return ExtractionSettings(
            seconds_per_frame=self.spf.value(),
            max_frames=self.max_frames.value(),
            start_time_seconds=self.start_time.value(),
            end_time_seconds=self.end_time.value(),
        ).validate()

    def _update_estimate(self):
        if self.track_type in {PANORAMA_VIDEO, ORDINARY_VIDEO}:
            if self._duration is None and self.loading_bar.isVisible():
                self.estimate_label.setText("正在加载素材")
                return
            try:
                settings = self._video_settings()
            except ValueError as exc:
                self.estimate_label.setText(str(exc))
                return
            count = estimate_video_frame_count(self._duration, settings)
            if count is None:
                text = "预计帧数未知"
            elif self.track_type == PANORAMA_VIDEO:
                text = f"预计{count}帧，{count * 2}张鱼眼"
            else:
                text = f"预计{count}帧"
            self.estimate_label.setText(text)
            return
        selected, total = estimate_photo_selection(self._photo_total, self.max_photos.value())
        self.estimate_label.setText(f"{selected}/{total}")

    def result_extraction(self):
        if self.track_type in {PANORAMA_VIDEO, ORDINARY_VIDEO}:
            return self._video_settings()
        return self.extraction

    def result_photo_limit(self):
        if self.track_type in {STANDARD_PHOTOS, AERIAL_PHOTOS}:
            selected, _total = estimate_photo_selection(self._photo_total, self.max_photos.value())
            return selected
        return 0

    def result_media_duration_seconds(self):
        return self._duration


def track_count_text(track: WorkbenchTrack):
    if track.track_type in {STANDARD_PHOTOS, AERIAL_PHOTOS}:
        try:
            total = len(photo_paths_from_material(track.paths))
            selected, total = estimate_photo_selection(total, track.photo_limit)
            return f"{selected}/{total}"
        except Exception:
            return "照片"
    if track.track_type in {PANORAMA_VIDEO, ORDINARY_VIDEO}:
        count = estimate_video_frame_count(track.media_duration_seconds, track.extraction)
        if count is None:
            return "预计--"
        if track.track_type == PANORAMA_VIDEO:
            return f"{count * 2}张"
        return f"{count}张"
    return ""


class TrackRowWidget(QWidget):
    def __init__(self, track: WorkbenchTrack, settings_callback, delete_callback, parent=None):
        super().__init__(parent)
        self.track_id = track.track_id
        self._settings_callback = settings_callback
        self._delete_callback = delete_callback
        self.setObjectName("TrackRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(make_icon(track_icon_name(track.track_type)).pixmap(22, 22))
        layout.addWidget(icon)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self.name_label = MarqueeLabel(track.label)
        self.name_label.setObjectName("TrackName")
        self.type_label = QLabel(track_type_title(track.track_type))
        self.type_label.setObjectName("MutedLabel")
        text_col.addWidget(self.name_label)
        text_col.addWidget(self.type_label)
        layout.addLayout(text_col, 1)
        self.delete_button = QToolButton()
        self.delete_button.setObjectName("DeleteIconButton")
        self.delete_button.setIcon(make_icon("close"))
        self.delete_button.setToolTip("删除素材轨")
        self.delete_button.clicked.connect(lambda: self._delete_callback(self.track_id))
        layout.addWidget(self.delete_button)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("IconButton")
        self.settings_button.setIcon(make_icon("env"))
        self.settings_button.setToolTip("素材轨设置")
        self.settings_button.clicked.connect(lambda: self._settings_callback(self.track_id))
        layout.addWidget(self.settings_button)
        self.count_label = QLabel("")
        self.count_label.setObjectName("CountCapsule")
        layout.addWidget(self.count_label)
        self.update_track(track)

    def update_track(self, track: WorkbenchTrack):
        self.track_id = track.track_id
        self.name_label.setText(track.label)
        self.type_label.setText(track_type_title(track.track_type))
        self.count_label.setText(track_count_text(track))


class InspectorPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._track = None
        self.setObjectName("InspectorPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.type_label = QLabel("")
        self.type_label.setObjectName("MutedLabel")
        self.type_label.setWordWrap(True)
        layout.addWidget(self.type_label)
        layout.addWidget(SectionTitle("抽帧"))

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.spf = QDoubleSpinBox()
        self.spf.setRange(0.01, 9999.0)
        self.spf.setDecimals(2)
        self.spf.setSingleStep(0.25)
        form.addRow("秒/帧", self.spf)

        self.max_frames = QSpinBox()
        self.max_frames.setRange(0, 1_000_000)
        self.max_frames.setSpecialValueText("全部")
        form.addRow("帧数", self.max_frames)

        self.start_time = QDoubleSpinBox()
        self.start_time.setRange(0.0, 1_000_000.0)
        self.start_time.setSuffix(" s")
        form.addRow("开始", self.start_time)

        self.end_time = QDoubleSpinBox()
        self.end_time.setRange(0.0, 1_000_000.0)
        self.end_time.setSuffix(" s")
        form.addRow("结束", self.end_time)
        layout.addLayout(form)
        layout.addWidget(SectionTitle("后端"))

        self.metashape_enabled = QCheckBox("Metashape")
        self.colmap_enabled = QCheckBox("COLMAP")
        layout.addWidget(self.metashape_enabled)
        layout.addWidget(self.colmap_enabled)
        layout.addStretch(1)
        self.set_track(None)

    def set_track(self, track: WorkbenchTrack | None):
        self._track = track
        enabled = track is not None
        for widget in [
            self.spf,
            self.max_frames,
            self.start_time,
            self.end_time,
            self.metashape_enabled,
            self.colmap_enabled,
        ]:
            widget.setEnabled(enabled)
        if not track:
            self.type_label.setText("")
            self.spf.setValue(1.0)
            self.max_frames.setValue(0)
            self.start_time.setValue(0.0)
            self.end_time.setValue(0.0)
            self.metashape_enabled.setChecked(False)
            self.colmap_enabled.setChecked(False)
            return
        primary = Path(track.paths[0]).name
        type_labels = {
            PANORAMA_VIDEO: "全景",
            ORDINARY_VIDEO: "视频",
            STANDARD_PHOTOS: "图片",
            AERIAL_PHOTOS: "航拍",
        }
        self.type_label.setText(f"{type_labels.get(track.track_type, track.display_type)}  -  {primary}")
        self.spf.setValue(track.extraction.seconds_per_frame)
        self.max_frames.setValue(track.extraction.max_frames)
        self.start_time.setValue(track.extraction.start_time_seconds)
        self.end_time.setValue(track.extraction.end_time_seconds)
        self.metashape_enabled.setChecked(track.enabled_for_metashape)
        self.colmap_enabled.setChecked(track.enabled_for_colmap)

    def edited_track(self):
        if not self._track:
            return None
        extraction = ExtractionSettings(
            seconds_per_frame=self.spf.value(),
            max_frames=self.max_frames.value(),
            start_time_seconds=self.start_time.value(),
            end_time_seconds=self.end_time.value(),
        ).validate()
        return replace(
            self._track,
            extraction=extraction,
            enabled_for_metashape=self.metashape_enabled.isChecked(),
            enabled_for_colmap=self.colmap_enabled.isChecked(),
        ).validate()


class FisheyePane(QWidget):
    def __init__(self, label, accent):
        super().__init__()
        self.label = label
        self.accent = QColor(accent)
        self.pixmap = None
        self.setMinimumSize(260, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0a0f19"))
        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            radius = min(self.width(), self.height()) * 0.32
            center = self.rect().center()
            painter.setPen(QPen(QColor("#2a3650"), 2))
            painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))
            painter.setPen(QPen(self.accent, 1.4))
            for index in range(8):
                angle = index * math.pi / 4
                painter.drawLine(
                    center.x(),
                    center.y(),
                    center.x() + math.cos(angle) * radius,
                    center.y() + math.sin(angle) * radius,
                )
        painter.setPen(QColor("#dbeafe"))
        painter.drawText(18, 28, self.label)
        painter.end()


class LiveReconstructionPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("LiveReconstructionPreview")
        self.scene = None
        self.show_camera_frustums = True
        self.setMinimumHeight(260)

    def set_scene(self, scene):
        self.scene = scene
        self.update()

    def set_camera_frustums_visible(self, visible):
        self.show_camera_frustums = bool(visible)
        self.update()

    def mousePressEvent(self, event):
        if getattr(self, "_frustum_toggle_rect", None) and self._frustum_toggle_rect.contains(event.position()):
            self.set_camera_frustums_visible(True)
            return
        if getattr(self, "_hide_toggle_rect", None) and self._hide_toggle_rect.contains(event.position()):
            self.set_camera_frustums_visible(False)
            return
        super().mousePressEvent(event)

    @staticmethod
    def _project_world_to_preview(xyz, center_x, center_y, scale, width, height):
        x, y, _z = xyz
        return (
            width / 2 + (x - center_x) * scale,
            height / 2 + (y - center_y) * scale,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0d0f10"))
        self._draw_background_grid(painter)
        if self.scene is None:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "等待 COLMAP snapshot")
            self._draw_hud(painter, 0, 0)
            painter.end()
            return

        positions = [camera.position for camera in self.scene.cameras]
        points = [point.xyz for point in self.scene.sparse_points[:6000]]
        all_xyz = positions + points
        if not all_xyz:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "snapshot 暂无点云")
            self._draw_hud(painter, 0, 0)
            painter.end()
            return

        xs = [xyz[0] for xyz in all_xyz]
        ys = [xyz[1] for xyz in all_xyz]
        xs_sorted = sorted(xs)
        ys_sorted = sorted(ys)
        trim = 0.02 if len(all_xyz) > 100 else 0.0
        low = int(len(all_xyz) * trim)
        high = max(low + 1, int(len(all_xyz) * (1.0 - trim)) - 1)
        min_x, max_x = xs_sorted[low], xs_sorted[high]
        min_y, max_y = ys_sorted[low], ys_sorted[high]
        span = max(max_x - min_x, max_y - min_y, 1e-6)
        margin = 30
        scale = min((self.width() - margin * 2) / span, (self.height() - margin * 2) / span)
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0

        def project(xyz):
            return self._project_world_to_preview(xyz, center_x, center_y, scale, self.width(), self.height())

        self._draw_axis_gizmo(painter)

        painter.setPen(Qt.NoPen)
        point_count = len(points)
        if point_count:
            step = max(1, point_count // 6000)
            for point in self.scene.sparse_points[::step]:
                px, py = project(point.xyz)
                painter.setBrush(QColor(int(point.rgb[0]), int(point.rgb[1]), int(point.rgb[2]), 185))
                painter.drawEllipse(QRectF(px - 1.2, py - 1.2, 2.4, 2.4))

        if len(positions) >= 2:
            painter.setPen(QPen(QColor("#22c55e"), 2.1))
            previous = project(positions[0])
            for position in positions[1:]:
                current = project(position)
                painter.drawLine(previous[0], previous[1], current[0], current[1])
                previous = current

        if self.show_camera_frustums:
            painter.setPen(QPen(QColor("#93c5fd"), 1.5))
            painter.setBrush(QColor(96, 165, 250, 75))
            camera_step = max(1, len(positions) // 280)
            sampled_positions = positions[::camera_step]
            projected_positions = [project(position) for position in sampled_positions]
            for index, projected in enumerate(projected_positions):
                if len(projected_positions) >= 2:
                    if index < len(projected_positions) - 1:
                        next_point = projected_positions[index + 1]
                        direction = (next_point[0] - projected[0], next_point[1] - projected[1])
                    else:
                        previous = projected_positions[index - 1]
                        direction = (projected[0] - previous[0], projected[1] - previous[1])
                else:
                    direction = (0.0, -1.0)
                self._draw_camera_frustum(painter, projected, direction)

        self._draw_hud(painter, len(self.scene.sparse_points), len(self.scene.cameras))
        painter.end()

    def _draw_background_grid(self, painter):
        painter.save()
        painter.setPen(QPen(QColor(31, 41, 55, 95), 1))
        spacing = 44
        for x in range(-self.height(), self.width() + self.height(), spacing):
            painter.drawLine(x, 0, x + self.height(), self.height())
        for x in range(0, self.width() + self.height() * 2, spacing):
            painter.drawLine(x, 0, x - self.height(), self.height())
        painter.restore()

    def _draw_axis_gizmo(self, painter):
        base_x = 22
        base_y = self.height() - 26
        painter.save()
        painter.setPen(QPen(QColor("#64748b"), 1.2))
        painter.drawLine(base_x, base_y, base_x + 58, base_y)
        painter.drawLine(base_x, base_y, base_x, base_y + 48)
        painter.setPen(QPen(QColor("#f97316"), 2.0))
        painter.drawLine(base_x, base_y, base_x + 58, base_y)
        painter.setPen(QColor("#f97316"))
        painter.drawText(QRectF(base_x + 64, base_y - 12, 34, 22), Qt.AlignLeft | Qt.AlignVCenter, "X+")
        painter.setPen(QPen(QColor("#22c55e"), 2.0))
        painter.drawLine(base_x + 16, base_y - 8, base_x + 16, base_y + 44)
        painter.setPen(QColor("#22c55e"))
        painter.drawText(QRectF(base_x + 22, base_y + 22, 80, 22), Qt.AlignLeft | Qt.AlignVCenter, "Y+")
        painter.restore()

    def _draw_camera_frustum(self, painter, projected, direction):
        px, py = projected
        dx, dy = direction
        length = math.hypot(dx, dy)
        if length < 1e-6:
            dx, dy = 0.0, -1.0
        else:
            dx, dy = dx / length, dy / length
        nx, ny = -dy, dx
        cone_length = 15.0
        half_width = 8.0
        apex = QPointF(px, py)
        center = QPointF(px + dx * cone_length, py + dy * cone_length)
        left = QPointF(center.x() + nx * half_width, center.y() + ny * half_width)
        right = QPointF(center.x() - nx * half_width, center.y() - ny * half_width)
        painter.drawPolygon(QPolygonF([apex, left, right]))
        painter.setBrush(QColor("#93c5fd"))
        painter.drawEllipse(QRectF(px - 2.2, py - 2.2, 4.4, 4.4))

    def _draw_hud(self, painter, point_count, camera_count):
        painter.save()
        y = self.height() - 64
        x = 16
        point_rect = self._draw_metric_pill(painter, x, y, "#f97316", "点数", f"{point_count:,}")
        x = point_rect.right() + 10
        camera_rect = self._draw_metric_pill(painter, x, y, "#22c55e", "相机", f"{camera_count:,}")
        x = camera_rect.right() + 14
        self._frustum_toggle_rect = QRectF(x, y, 82, 42)
        self._hide_toggle_rect = QRectF(x + 82, y, 82, 42)
        self._draw_segment(painter, self._frustum_toggle_rect, "视锥", self.show_camera_frustums, left=True)
        self._draw_segment(painter, self._hide_toggle_rect, "隐藏", not self.show_camera_frustums, right=True)
        painter.restore()

    def _draw_metric_pill(self, painter, x, y, color, label, value):
        rect = QRectF(x, y, 190, 42)
        painter.setPen(QPen(QColor(38, 45, 55, 210), 1))
        painter.setBrush(QColor(10, 13, 16, 218))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(x + 15, y + 17, 8, 8))
        painter.setPen(QColor("#7f8794"))
        painter.setFont(QFont(QApplication.font().family(), 10, QFont.Bold))
        painter.drawText(QRectF(x + 35, y + 8, 58, 26), Qt.AlignLeft | Qt.AlignVCenter, label)
        painter.setPen(QColor("#e5e7eb"))
        painter.drawText(QRectF(x + 92, y + 8, 86, 26), Qt.AlignLeft | Qt.AlignVCenter, value)
        return rect

    def _draw_segment(self, painter, rect, text, active, left=False, right=False):
        path_radius = 9
        painter.setPen(QPen(QColor(38, 45, 55, 210), 1))
        painter.setBrush(QColor("#2a2e33") if active else QColor(10, 13, 16, 218))
        painter.drawRoundedRect(rect, path_radius, path_radius)
        painter.setPen(QColor("#f1f5f9") if active else QColor("#64748b"))
        painter.setFont(QFont(QApplication.font().family(), 10, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, text)


class StageCanvas(QWidget):
    MODES = {"idle": 0, "extraction": 1, "alignment": 2, "export": 3}

    def __init__(self):
        super().__init__()
        self.setObjectName("StageCanvas")
        self.signals = None
        self.scene: ReconstructionScene | None = None
        self.viser_html_path = None
        self._last_viewer_error = None
        self._activity_title = ""
        self._activity_subtitle = ""
        self._runtime_camera_count = 0
        self._viewer_generation = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QWidget()
        self.header.setObjectName("StageHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(24, 18, 24, 12)
        self.stage_title = QLabel("就绪")
        self.stage_title.setObjectName("StageTitle")
        self.stage_subtitle = QLabel("")
        self.stage_subtitle.setObjectName("StageSubtitle")
        title_stack = QVBoxLayout()
        title_stack.setSpacing(3)
        title_stack.addWidget(self.stage_title)
        title_stack.addWidget(self.stage_subtitle)
        header_layout.addLayout(title_stack)
        header_layout.addStretch(1)
        self.stage_badge = QLabel("就绪")
        self.stage_badge.setObjectName("StageBadge")
        header_layout.addWidget(self.stage_badge)
        layout.addWidget(self.header)

        self.stack = QStackedWidget()
        self.stack.setObjectName("StageStack")
        self.stack.addWidget(self._build_idle_view())
        self.stack.addWidget(self._build_extraction_view())
        self.stack.addWidget(self._build_alignment_view())
        self.stack.addWidget(self._build_export_view())
        layout.addWidget(self.stack, 1)

        footer = QWidget()
        footer.setObjectName("StageFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(24, 10, 24, 18)
        footer_layout.setSpacing(8)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        footer_layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("WorkbenchLog")
        self.log.setMinimumHeight(108)
        self.log.setMaximumHeight(140)
        footer_layout.addWidget(self.log)
        layout.addWidget(footer)

    def set_signals(self, signals):
        self.signals = signals

    def _build_idle_view(self):
        view = QWidget()
        view.setObjectName("StageView")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(38, 20, 38, 20)
        layout.addStretch(1)
        title = QLabel("导入素材/拖入colmap文件夹")
        title.setObjectName("HeroTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("将素材拖入到此处")
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        return view

    def _build_extraction_view(self):
        view = QWidget()
        view.setObjectName("StageView")
        layout = QHBoxLayout(view)
        layout.setContentsMargins(24, 10, 24, 14)
        layout.setSpacing(2)
        self.left_preview = FisheyePane("左鱼眼", "#38bdf8")
        self.right_preview = FisheyePane("右鱼眼", "#22c55e")
        divider = QFrame()
        divider.setObjectName("StageDivider")
        divider.setFrameShape(QFrame.VLine)
        layout.addWidget(self.left_preview, 1)
        layout.addWidget(divider)
        layout.addWidget(self.right_preview, 1)
        return view

    def _build_alignment_view(self):
        view = QWidget()
        view.setObjectName("StageView")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(24, 10, 24, 14)
        layout.setSpacing(0)
        self.viser_view = None
        self.viewer_placeholder = QLabel("正在加载点云查看器")
        self.viewer_placeholder.setObjectName("ViewerPlaceholder")
        self.viewer_placeholder.setAlignment(Qt.AlignCenter)
        self.viewer_placeholder.setWordWrap(True)
        self.live_preview = LiveReconstructionPreview()
        layout.addWidget(self.live_preview, 1)
        if QWebEngineView is not None:
            self.viewer_placeholder.setText("等待 COLMAP 写出完整模型")
            layout.addWidget(self.viewer_placeholder, 1)
            self.viser_view = QWebEngineView()
            self.viser_view.setObjectName("ViserView")
            self.viser_view.hide()
            layout.addWidget(self.viser_view, 1)
        else:
            self.viewer_placeholder.setText("点云查看器不可用：请安装 PySide6-WebEngine")
            layout.addWidget(self.viewer_placeholder, 1)
        self.viewer_placeholder.hide()
        metrics = QWidget()
        metrics.setObjectName("MetricsStrip")
        metrics_layout = QHBoxLayout(metrics)
        metrics_layout.setContentsMargins(0, 10, 0, 0)
        metrics_layout.setSpacing(18)
        self.metric_backend = QLabel("后端 --")
        self.metric_backend.setObjectName("StageMetric")
        self.metric_progress = QLabel("进度 0%")
        self.metric_progress.setObjectName("StageMetric")
        self.metric_tracks = QLabel("素材 0")
        self.metric_tracks.setObjectName("StageMetric")
        self.compare_dense = QCheckBox("对比致密化")
        self.compare_dense.setObjectName("DenseCompareSwitch")
        self.compare_dense.setEnabled(False)
        self.compare_dense.toggled.connect(self._on_compare_dense_toggled)
        metrics_layout.addWidget(self.metric_backend)
        metrics_layout.addWidget(self.metric_progress)
        metrics_layout.addWidget(self.metric_tracks)
        metrics_layout.addStretch(1)
        metrics_layout.addWidget(self.compare_dense)
        layout.addWidget(metrics)
        return view

    def _build_export_view(self):
        view = QWidget()
        view.setObjectName("StageView")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(38, 20, 38, 20)
        layout.addStretch(1)
        self.export_label = QLabel("导出中")
        self.export_label.setObjectName("HeroTitle")
        self.export_label.setAlignment(Qt.AlignCenter)
        self.export_subtitle = QLabel("")
        self.export_subtitle.setObjectName("HeroSubtitle")
        self.export_subtitle.setAlignment(Qt.AlignCenter)
        self.export_subtitle.setWordWrap(True)
        layout.addWidget(self.export_label)
        layout.addWidget(self.export_subtitle)
        layout.addStretch(1)
        return view

    def set_mode(self, mode):
        mode = mode if mode in self.MODES else "idle"
        self.stack.setCurrentIndex(self.MODES[mode])
        titles = {
            "idle": ("就绪", "", "就绪"),
            "extraction": ("抽帧", "", "抽帧"),
            "alignment": ("重建查看", "", "对齐"),
            "export": ("导出", "", "导出"),
        }
        title, subtitle, badge = titles[mode]
        self.stage_title.setText(title)
        self.stage_subtitle.setText(subtitle)
        self.stage_badge.setText(badge)

    def set_activity(self, title, subtitle="", badge=None, mode=None):
        if mode:
            self.set_mode(mode)
        self._activity_title = str(title or "")
        self._activity_subtitle = str(subtitle or "")
        if self._activity_title:
            self.stage_title.setText(self._activity_title)
        self.stage_subtitle.setText(self._activity_subtitle)
        if badge:
            self.stage_badge.setText(str(badge))

    def set_runtime_alignment_preview(self, registered_count=None, image_index=None, total_images=None, detail=""):
        self.set_mode("alignment")
        if registered_count is not None:
            self._runtime_camera_count = max(self._runtime_camera_count, int(registered_count))
        title = "COLMAP 相机对齐"
        pieces = []
        if self._runtime_camera_count:
            pieces.append(f"已注册相机 {self._runtime_camera_count}")
        if image_index is not None:
            if total_images:
                pieces.append(f"当前图像 {int(image_index)}/{int(total_images)}")
            else:
                pieces.append(f"当前图像 {int(image_index)}")
        if detail:
            pieces.append(str(detail))
        self.set_activity(title, "，".join(pieces) or "正在增量注册相机", "对齐", "alignment")
        if self.live_preview.scene is None:
            self.live_preview.show()
        if self.viser_view is not None and self.viser_view.isVisible():
            self.viser_view.hide()
        if self.live_preview.scene is None:
            self.viewer_placeholder.setText(
                "COLMAP 正在等待首个真实 snapshot\n"
                f"已注册相机：{self._runtime_camera_count or '--'}"
            )
            if self.viewer_placeholder.parent() is not None:
                self.viewer_placeholder.show()

    def update_runtime_preview_from_log(self, text):
        text = str(text)
        registered = None
        image_index = None
        total_images = None
        match = re.search(r"Registering image #(\d+)\s*\(num_reg_frames=(\d+)\)", text)
        if match:
            image_index = int(match.group(1))
            registered = int(match.group(2))
        match = re.search(r"Image sees \d+\s*/\s*(\d+)", text)
        if match:
            total_images = int(match.group(1))
        if registered is not None or "registering image" in text.lower():
            self.set_runtime_alignment_preview(
                registered_count=registered,
                image_index=image_index,
                total_images=total_images,
                detail=text if registered is None else "",
            )

    def update_activity_from_log(self, text):
        text = str(text)
        lowered = text.lower()
        if "colmap_stage: feature_extraction" in lowered:
            self.set_activity("COLMAP 特征点提取", "正在读取双鱼眼图像并提取 SIFT 特征", "特征", "alignment")
        elif "colmap_stage: feature_matching" in lowered:
            self.set_activity("COLMAP 特征匹配", "正在按时间序列建立相邻帧匹配关系", "匹配", "alignment")
        elif "colmap_stage: mapping" in lowered:
            self.set_activity("COLMAP 相机对齐", "正在增量注册相机并生成稀疏点云", "对齐", "alignment")
        elif "colmap_stage_done: mapper" in lowered:
            self.set_activity("COLMAP 稀疏重建完成", "正在转换为训练可用的 COLMAP 目录", "导出", "export")
        if "colmap feature_extractor" in lowered:
            self.set_activity("COLMAP 特征点提取", "正在读取双鱼眼图像并提取 SIFT 特征", "特征", "alignment")
        elif "colmap sequential_matcher" in lowered or "colmap exhaustive_matcher" in lowered:
            self.set_activity("COLMAP 特征匹配", "正在按时间序列建立相邻帧匹配关系", "匹配", "alignment")
        elif "colmap mapper" in lowered:
            self.set_activity("COLMAP 相机对齐", "正在增量注册相机并生成稀疏点云", "对齐", "alignment")
        elif "starting incremental reconstruction" in lowered or "registering image" in lowered:
            self.set_activity("COLMAP 相机对齐", text, "对齐", "alignment")
            self.update_runtime_preview_from_log(text)
        elif "beginning extraction" in lowered or "feature extraction" in lowered:
            self.set_activity("COLMAP 特征点提取", text, "特征", "alignment")
        elif "matching block" in lowered or "feature matching" in lowered:
            self.set_activity("COLMAP 特征匹配", text, "匹配", "alignment")
        elif "publish" in lowered or "export" in lowered or "导出" in text:
            self.set_activity("导出 COLMAP", "正在写入训练可用的 COLMAP 目录", "导出", "export")

    def set_progress(self, value):
        value = max(0, min(100, int(value)))
        self.progress.setValue(value)
        self.metric_progress.setText(f"进度 {value}%")
        if value < 35:
            self.set_mode("extraction")
        elif value < 95:
            self.set_mode("alignment")
        else:
            self.set_mode("export")

    def set_backend(self, backend):
        self.metric_backend.setText(f"后端 {backend}")

    def set_track_count(self, count):
        self.metric_tracks.setText(f"素材 {count}")

    def append_log(self, text):
        self.log.append(str(text))
        self.update_activity_from_log(text)

    def set_reconstruction_scene(self, scene, live_only=False):
        self.scene = scene
        self.compare_dense.setEnabled(scene.has_dense_comparison)
        if not scene.has_dense_comparison:
            self.compare_dense.setChecked(False)
        self.live_preview.set_scene(scene)
        self.live_preview.show()
        if self.viser_view is not None:
            self.viser_view.hide()
        self.viewer_placeholder.hide()
        if not live_only:
            self._load_viser_scene(scene, compare_dense=self.compare_dense.isChecked())
        else:
            self.viewer_placeholder.hide()
            if self.viser_view is not None:
                self.viser_view.hide()
        self.set_mode("alignment")

    def load_scene_from_output(self, output_dir):
        scene = load_reconstruction_scene(output_dir)
        self.set_reconstruction_scene(scene)
        self.append_log(
            f"已载入：稀疏 {len(scene.sparse_points)} / 致密 {len(scene.dense_points)} / 相机 {len(scene.cameras)}"
        )
        return scene

    def _load_viser_scene(self, scene, compare_dense=False):
        try:
            if self.viser_view is None:
                raise RuntimeError("PySide6-WebEngine 未安装，无法嵌入点云查看器")
            if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
                raise RuntimeError("截图模式禁用 Qt WebEngine")
            from xpano_workbench.viser_bridge import write_viser_html

            self._viewer_generation += 1
            generation = self._viewer_generation
            self.viewer_placeholder.setText(
                f"正在生成点云预览\n相机 {len(scene.cameras)}，点 {len(scene.final_points)}"
            )
            self.viewer_placeholder.show()
            if self.viser_view is not None:
                self.viser_view.hide()

            def build_target():
                try:
                    path = write_viser_html(scene, compare_dense=compare_dense)
                    if self.signals is not None and generation == self._viewer_generation:
                        self.signals.viewer_ready.emit(str(path), len(scene.cameras), len(scene.final_points))
                except Exception as exc:
                    if self.signals is not None and generation == self._viewer_generation:
                        self.signals.viewer_error.emit(str(exc))

            threading.Thread(target=build_target, daemon=True).start()
        except Exception as exc:
            self.handle_viewer_error(str(exc))

    def load_viewer_html(self, html_path, camera_count, point_count):
        if self.viser_view is None:
            return
        self.viser_html_path = Path(html_path)
        self.viewer_placeholder.hide()
        self.live_preview.hide()
        self.viser_view.show()
        self.viser_view.load(QUrl.fromLocalFile(str(self.viser_html_path)))
        self.set_activity("重建查看", f"相机 {camera_count}，点 {point_count}", "预览", "alignment")

    def handle_viewer_error(self, message):
        message = str(message)
        self.viewer_placeholder.setText(f"点云查看器不可用：{message}")
        self.viewer_placeholder.show()
        if self.viser_view is not None:
            self.viser_view.hide()
        if message != self._last_viewer_error:
            self.append_log(f"点云查看器不可用：{message}")
            self._last_viewer_error = message

    def _on_compare_dense_toggled(self, enabled):
        if self.scene is not None:
            self._load_viser_scene(self.scene, compare_dense=enabled)

    def set_preview(self, left_path, right_path):
        self.set_mode("extraction")
        self._set_preview_image(self.left_preview, left_path)
        self._set_preview_image(self.right_preview, right_path)

    def set_demo_preview(self):
        self.left_preview.set_pixmap(make_demo_fisheye("左鱼眼", "#38bdf8"))
        self.right_preview.set_pixmap(make_demo_fisheye("右鱼眼", "#22c55e"))

    def _set_preview_image(self, pane, path):
        path = Path(path) if path else None
        if not path or not path.exists():
            pane.set_pixmap(None)
            return
        pixmap = QPixmap(str(path))
        pane.set_pixmap(None if pixmap.isNull() else pixmap)


class WorkbenchSignals(QObject):
    progress = Signal(int)
    log = Signal(str)
    plugin_log = Signal(str)
    preview = Signal(str, str)
    done = Signal(object)
    error = Signal(str)
    viewer_ready = Signal(str, int, int)
    viewer_error = Signal(str)


class QtEventSink(WorkbenchEventSink):
    def __init__(self, signals):
        self.signals = signals

    def progress(self, value):
        self.signals.progress.emit(int(value))

    def log(self, text):
        self.signals.log.emit(str(text))

    def preview(self, left_path, right_path):
        self.signals.preview.emit(str(left_path), str(right_path))

    def done(self, result=None):
        self.signals.done.emit(result)

    def error(self, exc):
        self.signals.error.emit(str(exc))


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("Splash")
        self.resize(360, 180)
        self.setStyleSheet(
            """
            QWidget#Splash {
                background: #0b1220;
                border-radius: 18px;
            }
            QLabel#SplashTitle {
                color: #f8fafc;
                font-size: 26pt;
                font-weight: 760;
            }
            QLabel#SplashSubtitle {
                color: #94a3b8;
                font-size: 11pt;
            }
            QProgressBar {
                background: #1e293b;
                border: 0;
                border-radius: 5px;
                height: 10px;
                color: transparent;
            }
            QProgressBar::chunk {
                background: #22c55e;
                border-radius: 5px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(14)
        title = QLabel("xPano")
        title.setObjectName("SplashTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("工作台")
        subtitle.setObjectName("SplashSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(self.bar)
        layout.addStretch(1)
        self._value = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(24)

    def _tick(self):
        self._value = min(100, self._value + 5)
        self.bar.setValue(self._value)


class WorkbenchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tracks: list[WorkbenchTrack] = []
        self.running = False
        self.densifying = False
        self.output_dir_manually_set = False
        self.stop_requested = False
        self.signals = WorkbenchSignals()
        self.headless_mode = os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"
        self._colmap_scene_signature = None
        self._colmap_scene_timer = QTimer(self)
        self._colmap_scene_timer.setInterval(4000)
        self._colmap_scene_timer.timeout.connect(self._try_load_incremental_colmap_scene)
        self._colmap_mapping_finished = False
        self.setWindowTitle(f"xPano 工作台 {__version__}")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 700)
        self.setAcceptDrops(True)
        self._build_actions()
        self._build_layout()
        self._connect_signals()
        self._apply_style()
        self._apply_default_backend()

    def _build_actions(self):
        self.import_pano_action = QAction(make_icon("pano"), "全景", self)
        self.import_pano_action.triggered.connect(self.add_panorama_track)
        self.import_ordinary_action = QAction(make_icon("video"), "视频", self)
        self.import_ordinary_action.triggered.connect(self.add_ordinary_video_track)
        self.import_photos_action = QAction(make_icon("folder"), "图片", self)
        self.import_photos_action.triggered.connect(self.add_photo_track)
        self.environment_action = QAction(make_icon("env"), "环境", self)
        self.environment_action.triggered.connect(lambda: self.stage.append_log("环境检查会在发布版中自动执行。"))
        self.run_action = QAction(make_icon("run", "#f8fafc"), "开始", self)
        self.run_action.triggered.connect(self.start_run)
        self.stop_action = QAction(make_icon("stop"), "Stop", self)
        self.stop_action.setEnabled(False)
        self.output_action = QAction(make_icon("output"), "输出", self)
        self.output_action.triggered.connect(self.pick_output_dir)
        self.densify_action = QAction(make_icon("env", "#f8fafc"), "致密化", self)
        self.densify_action.triggered.connect(self.start_densify_current_scene)

    def _build_layout(self):
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("RootSplitter")
        splitter.addWidget(self._build_left_workspace())
        self.stage = StageCanvas()
        self.stage.set_signals(self.signals)
        splitter.addWidget(self.stage)
        splitter.setSizes([470, 970])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)
        root_layout.addWidget(self._build_bottom_bar())
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")

    def _build_top_bar(self):
        bar = QWidget()
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(10)
        brand = QLabel("xPano")
        brand.setObjectName("Brand")
        version = QLabel(f"工作台 {__version__}")
        version.setObjectName("MutedLabel")
        layout.addWidget(brand)
        layout.addWidget(version)
        layout.addStretch(1)
        return bar

    def _build_bottom_bar(self):
        bar = QWidget()
        bar.setObjectName("BottomBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 8, 18, 10)
        layout.addStretch(1)
        self.start_stop_button = QPushButton("开始")
        self.start_stop_button.setObjectName("BottomRunButton")
        self.start_stop_button.setProperty("running", False)
        self.start_stop_button.setIcon(make_icon("run"))
        self.start_stop_button.clicked.connect(self.toggle_run)
        layout.addWidget(self.start_stop_button)
        layout.addStretch(1)
        return bar

    def _tool_button(self, action):
        button = QToolButton()
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _build_left_workspace(self):
        workspace = QWidget()
        workspace.setObjectName("LeftWorkspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("InspectorScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls = QWidget()
        controls.setObjectName("ControlsPane")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.setSpacing(10)

        controls_layout.addWidget(self._build_tracks_section())
        self.inspector = None
        controls_layout.addWidget(self._build_run_section())
        controls_layout.addWidget(self._build_plugin_section())
        controls_layout.addStretch(1)
        scroll.setWidget(controls)
        layout.addWidget(scroll, 1)
        return workspace

    def _build_tracks_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("素材")
        title.setObjectName("PanelTitle")
        header.addWidget(title)
        header.addStretch(1)
        add_button = QToolButton()
        add_button.setObjectName("AddMaterialButton")
        add_button.setIcon(make_icon("plus"))
        add_button.setToolTip("添加素材")
        add_button.clicked.connect(self.add_material_track)
        header.addWidget(add_button)
        layout.addLayout(header)
        self.track_list = QListWidget()
        self.track_list.setObjectName("TrackList")
        self.track_list.setMinimumHeight(168)
        self.track_list.currentItemChanged.connect(self._on_track_selected)
        layout.addWidget(self.track_list)
        return section

    def _build_run_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(SectionTitle("配置"))
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        self.output_dir = QLineEdit()
        self.output_dir.textEdited.connect(self._mark_output_dir_manual)
        output_button = QPushButton("选择")
        output_button.clicked.connect(self.pick_output_dir)
        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.addWidget(self.output_dir, 1)
        output_row.addWidget(output_button)
        form.addRow("输出", output_row)
        self.backend_combo = BackendSwitch("metashape")
        self.backend_combo.changed.connect(self.stage_backend_changed)
        form.addRow("后端", self.backend_combo)
        layout.addLayout(form)

        advanced = CollapsibleSection("高级参数", expanded=False)
        advanced_form = QFormLayout()
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setHorizontalSpacing(12)
        advanced_form.setVerticalSpacing(10)
        self.metashape_exe = QLineEdit("metashape.exe")
        advanced_form.addRow("Metashape", self.metashape_exe)
        self.colmap_exe = QLineEdit(locate_colmap())
        advanced_form.addRow("COLMAP", self.colmap_exe)
        self.colmap_density = QComboBox()
        self.colmap_density.addItems(["stable", "high-density"])
        advanced_form.addRow("密度", self.colmap_density)
        self.colmap_gpu = QCheckBox("CUDA")
        self.colmap_gpu.setChecked(True)
        advanced_form.addRow(self.colmap_gpu)
        advanced_body = QWidget()
        advanced_body.setLayout(advanced_form)
        advanced.addWidget(advanced_body)
        layout.addWidget(advanced)
        self.advanced_section = advanced
        return section

    def _build_plugin_section(self):
        section = QWidget()
        section.setObjectName("PluginSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(SectionTitle("插件"))
        self.densify_plugin = CollapsibleSection("致密化插件", expanded=False)
        plugin_body = QWidget()
        plugin_form = QFormLayout(plugin_body)
        plugin_form.setContentsMargins(0, 0, 0, 0)
        plugin_form.setHorizontalSpacing(12)
        plugin_form.setVerticalSpacing(8)
        self.plugin_cuda = QCheckBox("CUDA")
        self.plugin_cuda.setChecked(True)
        plugin_form.addRow(self.plugin_cuda)
        self.lfs_max_points = QSpinBox()
        self.lfs_max_points.setRange(0, 10_000_000)
        self.lfs_max_points.setSingleStep(50_000)
        self.lfs_max_points.setSpecialValueText("不限")
        plugin_form.addRow("点数", self.lfs_max_points)
        self.plugin_run_button = QPushButton("启动致密化")
        self.plugin_run_button.setObjectName("PluginRunButton")
        self.plugin_run_button.clicked.connect(self.start_densify_current_scene)
        plugin_form.addRow(self.plugin_run_button)
        self.plugin_log = QTextEdit()
        self.plugin_log.setObjectName("PluginLog")
        self.plugin_log.setReadOnly(True)
        self.plugin_log.setMaximumHeight(92)
        self.densify_plugin.addWidget(plugin_body)
        self.densify_plugin.addWidget(self.plugin_log)
        layout.addWidget(self.densify_plugin)
        self.set_densify_plugin_enabled(False)
        return section

    def _connect_signals(self):
        self.signals.progress.connect(self.stage.set_progress)
        self.signals.log.connect(self._on_pipeline_log)
        self.signals.plugin_log.connect(self.append_plugin_log)
        self.signals.preview.connect(self.stage.set_preview)
        self.signals.done.connect(self._on_run_done)
        self.signals.error.connect(self._on_run_error)
        self.signals.viewer_ready.connect(self.stage.load_viewer_html)
        self.signals.viewer_error.connect(self.stage.handle_viewer_error)

    def _on_pipeline_log(self, text):
        text = str(text)
        self.stage.append_log(text)
        lowered = text.lower()
        if "colmap_stage: mapping" in lowered or "colmap mapper" in lowered or "starting incremental reconstruction" in lowered:
            self._colmap_mapping_finished = False
            self._start_colmap_scene_polling()
        elif "colmap_stage_done: mapper" in lowered:
            self._colmap_mapping_finished = True
            self._try_load_incremental_colmap_scene(force=True)
        elif "完成" in text or "colmap publish" in lowered or "导出" in text:
            self._colmap_scene_timer.stop()

    def _start_colmap_scene_polling(self):
        if self.backend_combo.currentText() != "colmap":
            return
        if not self._colmap_scene_timer.isActive():
            self._colmap_scene_timer.start()

    def _try_load_incremental_colmap_scene(self, force=False):
        if self.backend_combo.currentText() != "colmap":
            self._colmap_scene_timer.stop()
            return
        output = self.output_dir.text().strip()
        if not output:
            return
        try:
            scene = load_reconstruction_scene(
                output,
                max_sparse_points=45_000,
                max_dense_points=45_000,
                prefer_snapshots=not self._colmap_mapping_finished,
            )
        except Exception:
            return
        signature = (len(scene.sparse_points), len(scene.dense_points), len(scene.cameras), str(scene.sparse_path), str(scene.dense_path))
        if signature == self._colmap_scene_signature:
            return
        self._colmap_scene_signature = signature
        self.stage.set_reconstruction_scene(scene, live_only=not self._colmap_mapping_finished)
        self.stage.set_activity(
            "COLMAP 增量预览",
            f"已注册相机 {len(scene.cameras)}，稀疏点 {len(scene.sparse_points)}",
            "预览",
            "alignment",
        )

    def _apply_default_backend(self):
        self.colmap_gpu.setChecked(True)
        try:
            metashape = resolve_executable(self.metashape_exe.text().strip() or "metashape.exe", "metashape.exe")
            self.metashape_exe.setText(metashape)
            self.backend_combo.setCurrentText("metashape")
        except Exception as exc:
            self.backend_combo.setCurrentText("colmap")
            try:
                colmap = resolve_executable(self.colmap_exe.text().strip() or "colmap", "colmap")
                self.colmap_exe.setText(colmap)
            except Exception:
                pass
            message = f"未找到 Metashape，已自动切换到内置 COLMAP：{exc}"
            self.stage.append_log(message)
            self.statusBar().showMessage(message, 8000)
            if not self.headless_mode:
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "未找到 Metashape", message))

    def stage_backend_changed(self, backend):
        self.stage.set_backend(backend)

    def set_densify_plugin_enabled(self, enabled):
        enabled = bool(enabled)
        self.densify_plugin.setEnabled(enabled)
        self.plugin_run_button.setEnabled(enabled)
        self.densify_plugin.toggle_button.setText("致密化插件" if enabled else "致密化插件（需要 COLMAP 输出）")

    def append_plugin_log(self, text):
        self.plugin_log.append(str(text))

    def _next_index(self):
        return len(self.tracks) + 1

    def _track_by_id(self, track_id):
        return next((track for track in self.tracks if track.track_id == track_id), None)

    def _mark_output_dir_manual(self, _text=None):
        self.output_dir_manually_set = True

    def _ensure_default_output_dir(self, paths):
        if self.output_dir_manually_set or self.tracks:
            return
        if not paths:
            return
        source = Path(paths[0])
        root = source.parent
        output = root / "colmap"
        output.mkdir(parents=True, exist_ok=True)
        self.output_dir.blockSignals(True)
        self.output_dir.setText(str(output))
        self.output_dir.blockSignals(False)
        self.stage.append_log(f"输出目录：{output}")

    def add_material_track(self):
        dialog = MaterialTypeDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        track_type = dialog.selected_type
        if track_type == PANORAMA_VIDEO:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择全景视频",
                "",
                "全景视频 (*.osv *.insv *.mp4);;所有文件 (*.*)",
            )
            if path:
                self.import_material_paths([Path(path)], PANORAMA_VIDEO)
        elif track_type == ORDINARY_VIDEO:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择视频",
                "",
                "视频 (*.mp4 *.mov *.avi *.mkv);;所有文件 (*.*)",
            )
            if path:
                self.import_material_paths([Path(path)], ORDINARY_VIDEO)
        else:
            path = QFileDialog.getExistingDirectory(self, "选择照片文件夹")
            if path:
                self.import_material_paths([Path(path)], STANDARD_PHOTOS)

    def _append_track(self, track: WorkbenchTrack):
        self._sync_selected_track_from_inspector()
        self.tracks.append(track)
        item = TrackListItem(track)
        item.setSizeHint(QSize(0, 66))
        self.track_list.addItem(item)
        self.track_list.setItemWidget(item, TrackRowWidget(track, self.open_track_settings, self.remove_track_by_id))
        self.track_list.setCurrentItem(item)
        self.stage.set_track_count(len(self.tracks))
        self.statusBar().showMessage(f"已添加：{track.label}", 5000)

    def _refresh_track_item(self, track_id):
        track = self._track_by_id(track_id)
        if not track:
            return
        for row in range(self.track_list.count()):
            item = self.track_list.item(row)
            if getattr(item, "track_id", None) != track_id:
                continue
            widget = self.track_list.itemWidget(item)
            if isinstance(widget, TrackRowWidget):
                widget.update_track(track)
            item.setText("")
            return

    def open_track_settings(self, track_id):
        track = self._track_by_id(track_id)
        if not track:
            return
        try:
            dialog = TrackSettingsDialog(
                track.track_type,
                track.paths,
                extraction=track.extraction,
                photo_limit=track.photo_limit,
                media_duration_seconds=track.media_duration_seconds,
                parent=self,
            )
        except Exception as exc:
            QMessageBox.warning(self, "素材不可用", str(exc))
            return
        if dialog.exec() != QDialog.Accepted:
            return
        updated = replace(
            track,
            extraction=dialog.result_extraction(),
            photo_limit=dialog.result_photo_limit(),
            media_duration_seconds=dialog.result_media_duration_seconds(),
        ).validate()
        for index, item in enumerate(self.tracks):
            if item.track_id == track_id:
                self.tracks[index] = updated
                break
        self._refresh_track_item(track_id)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            paths.append(path)
        if not paths:
            event.ignore()
            return
        if len(paths) == 1 and paths[0].is_dir():
            if self.load_external_colmap_path(paths[0]):
                event.acceptProposedAction()
                return
        self.import_material_paths(paths)
        event.acceptProposedAction()

    def load_external_colmap_path(self, path):
        try:
            root = resolve_colmap_scene_root(path)
            self.output_dir.setText(str(root))
            self.stage.load_scene_from_output(root)
            self.set_densify_plugin_enabled(True)
            self.statusBar().showMessage(f"已载入 COLMAP：{root}", 5000)
            return True
        except Exception as exc:
            self.stage.append_log(f"无法载入 COLMAP：{exc}")
            return False

    def import_material_paths(self, paths, preset_type=None):
        paths = [Path(path) for path in paths]
        track_type = preset_type
        if track_type is None:
            dialog = MaterialTypeDialog(self)
            if dialog.exec() != QDialog.Accepted:
                return
            track_type = dialog.selected_type
        self._ensure_default_output_dir(paths)
        try:
            if track_type in {PANORAMA_VIDEO, ORDINARY_VIDEO}:
                for path in paths:
                    self._import_video_track(path, track_type)
            elif track_type == STANDARD_PHOTOS:
                self._import_photo_track(paths)
            else:
                raise ValueError(f"Unsupported material type: {track_type}")
        except Exception as exc:
            QMessageBox.warning(self, "素材导入失败", str(exc))

    def _import_video_track(self, path, track_type):
        path = Path(path)
        if not path.is_file():
            raise ValueError("视频/全景素材必须是文件")
        allowed = PANORAMA_EXTENSIONS if track_type == PANORAMA_VIDEO else VIDEO_EXTENSIONS
        if path.suffix.lower() not in allowed:
            raise ValueError(f"不支持的素材格式：{path.name}")
        dialog = TrackSettingsDialog(track_type, [path], parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._append_track(
            create_track(
                self._next_index(),
                track_type,
                path.stem,
                [path],
                extraction=dialog.result_extraction(),
                media_duration_seconds=dialog.result_media_duration_seconds(),
            )
        )

    def _import_photo_track(self, paths):
        photos = photo_paths_from_material(paths)
        label = Path(paths[0]).name if len(paths) == 1 else f"照片素材 {self._next_index()}"
        dialog = TrackSettingsDialog(STANDARD_PHOTOS, paths, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._append_track(
            create_track(
                self._next_index(),
                STANDARD_PHOTOS,
                label,
                paths,
                photo_limit=dialog.result_photo_limit() or len(photos),
            )
        )

    def remove_selected_track(self):
        current = self.track_list.currentItem()
        if not current:
            return
        self.remove_track_by_id(current.track_id)

    def remove_track_by_id(self, track_id):
        self.tracks = [track for track in self.tracks if track.track_id != track_id]
        for row in range(self.track_list.count()):
            item = self.track_list.item(row)
            if getattr(item, "track_id", None) == track_id:
                self.track_list.takeItem(row)
                break
        self.stage.set_track_count(len(self.tracks))

    def pick_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_manually_set = True
            self.output_dir.setText(path)
            try:
                self.stage.load_scene_from_output(path)
            except Exception:
                self.stage.append_log("已选择输出目录。")

    def start_densify_current_scene(self):
        if self.running or self.densifying:
            return
        output = self.output_dir.text().strip()
        if not output:
            QMessageBox.warning(self, "缺少目录", "请先选择或拖入 COLMAP 文件夹。")
            return
        try:
            root = resolve_colmap_scene_root(output)
        except Exception as exc:
            QMessageBox.warning(self, "无法致密化", str(exc))
            return
        self.densifying = True
        self.plugin_run_button.setEnabled(False)
        self.stage.set_mode("alignment")
        self.stage.set_progress(90)
        self.stage.append_log("开始致密化")
        self.append_plugin_log("开始致密化")

        job = SimpleNamespace(
            output_dir=root,
            lfs_densify_python=None,
            lfs_densify_plugin=None,
            lfs_densify_roma="fast",
            lfs_densify_num_refs=8.0,
            lfs_densify_max_points=self.lfs_max_points.value(),
        )

        def run_target():
            try:
                run_lfs_densification_stage(job, self.signals.progress.emit, self._emit_plugin_log)
                self.signals.done.emit({"densify_only": True, "output_dir": str(root)})
            except Exception as exc:
                self.signals.error.emit(str(exc))

        threading.Thread(target=run_target, daemon=True).start()

    def _emit_plugin_log(self, text):
        self.signals.log.emit(str(text))
        self.signals.plugin_log.emit(str(text))

    def _sync_selected_track_from_inspector(self):
        return

    def toggle_run(self):
        if self.running:
            self.stop_run()
        else:
            self.start_run()

    def _set_run_button_running(self, running):
        self.start_stop_button.setText("停止" if running else "开始")
        self.start_stop_button.setIcon(make_icon("stop" if running else "run"))
        self.start_stop_button.setProperty("running", running)
        self.start_stop_button.style().unpolish(self.start_stop_button)
        self.start_stop_button.style().polish(self.start_stop_button)

    def stop_run(self):
        if not self.running:
            return
        self.stop_requested = True
        self.stage.append_log("正在停止")
        self.statusBar().showMessage("正在停止", 3000)
        self._terminate_pipeline_processes()

    def _terminate_pipeline_processes(self):
        if os.name != "nt":
            return
        names = {"ffmpeg.exe"}
        for value in [self.colmap_exe.text().strip(), self.metashape_exe.text().strip()]:
            if not value:
                continue
            name = Path(value).name
            if not name.lower().endswith(".exe"):
                name = f"{name}.exe"
            names.add(name)
        for name in sorted(names):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/IM", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass

    def _resolved_backend_executables(self, backend):
        metashape = self.metashape_exe.text().strip() or "metashape.exe"
        colmap = self.colmap_exe.text().strip() or "colmap"
        if backend == "metashape":
            metashape = resolve_executable(metashape, "metashape.exe")
        if backend == "colmap":
            colmap = resolve_executable(colmap, "colmap")
            self.colmap_exe.setText(colmap)
        return metashape, colmap

    def start_run(self):
        if self.running:
            return
        self._sync_selected_track_from_inspector()
        if not self.tracks:
            QMessageBox.warning(self, "缺少素材", "请先添加素材。")
            return
        if not self.output_dir.text().strip():
            QMessageBox.warning(self, "缺少输出", "请选择输出目录。")
            return
        backend = self.backend_combo.currentText()
        try:
            metashape_exe, colmap_exe = self._resolved_backend_executables(backend)
        except Exception as exc:
            message = (
                "找不到 COLMAP 可执行文件。请把 colmap.exe 放到项目 tools/colmap/bin，"
                "或在 COLMAP 输入框填写完整路径。"
                if backend == "colmap"
                else str(exc)
            )
            self.stage.append_log(f"依赖错误：{exc}")
            QMessageBox.critical(self, "依赖错误", message)
            return
        config = WorkbenchRunConfig(
            tracks=tuple(self.tracks),
            output_dir=Path(self.output_dir.text().strip()),
            backend=backend,
            metashape_exe=metashape_exe,
            colmap_exe=colmap_exe,
            colmap_density_preset=self.colmap_density.currentText(),
            colmap_use_gpu=self.colmap_gpu.isChecked(),
            run_lfs_densify=False,
            lfs_densify_max_points=self.lfs_max_points.value(),
        )
        self.running = True
        self.stop_requested = False
        self._set_run_button_running(True)
        self.stage.set_backend(backend)
        self.stage.set_track_count(len(self.tracks))
        self.stage.set_progress(0)
        self._colmap_scene_signature = None
        self._colmap_mapping_finished = False
        self.stage._runtime_camera_count = 0
        if backend == "colmap":
            self._start_colmap_scene_polling()
        self.stage.append_log("开始")
        sink = QtEventSink(self.signals)

        def run_target():
            try:
                run_workbench_pipeline(config, sink)
            except Exception:
                pass

        thread = threading.Thread(target=run_target, daemon=True)
        thread.start()

    def _on_run_done(self, _result):
        self.running = False
        self.densifying = False
        self._set_run_button_running(False)
        self._colmap_scene_timer.stop()
        self.plugin_run_button.setEnabled(True)
        try:
            self.stage.load_scene_from_output(self.output_dir.text().strip())
            self.set_densify_plugin_enabled(True)
        except Exception as exc:
            self.stage.set_mode("export")
            self.stage.append_log(f"无法加载重建结果：{exc}")
        self.statusBar().showMessage("完成", 5000)
        self.stage.append_log("完成")

    def _on_run_error(self, message):
        self.running = False
        self.densifying = False
        self._set_run_button_running(False)
        self._colmap_scene_timer.stop()
        self.plugin_run_button.setEnabled(True)
        if self.stop_requested:
            self.stop_requested = False
            self.statusBar().showMessage("已停止", 5000)
            self.stage.append_log("已停止")
            return
        self.statusBar().showMessage("失败", 5000)
        self.stage.append_log(f"错误：{message}")
        QMessageBox.critical(self, "失败", message)

    def add_panorama_track(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "添加全景视频",
            "",
            "全景视频 (*.osv *.insv *.mp4);;所有文件 (*.*)",
        )
        if paths:
            self.import_material_paths(paths, PANORAMA_VIDEO)

    def add_ordinary_video_track(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "添加普通视频",
            "",
            "视频 (*.mp4 *.mov *.avi *.mkv);;所有文件 (*.*)",
        )
        if paths:
            self.import_material_paths(paths, ORDINARY_VIDEO)

    def add_photo_track(self):
        path = QFileDialog.getExistingDirectory(self, "添加图片文件夹")
        if path:
            self.import_material_paths([Path(path)], STANDARD_PHOTOS)

    def _on_track_selected(self, current, _previous):
        return

    def populate_demo(self, mode="alignment"):
        demo_path = Path(tempfile.gettempdir()) / "xpano_demo.osv"
        self._append_track(create_track(1, PANORAMA_VIDEO, "Qinshi dual fisheye", [demo_path]))
        self.output_dir.setText(str(Path(tempfile.gettempdir()) / "xpano_output"))
        self.backend_combo.setCurrentText("colmap")
        self.stage.set_backend("colmap")
        self.stage.set_track_count(len(self.tracks))
        self.stage.set_demo_preview()
        self.stage.set_reconstruction_scene(make_demo_reconstruction_scene())
        self.stage.append_log("抽帧 000042")
        self.stage.append_log("COLMAP 对齐中")
        if mode == "extraction":
            self.stage.set_mode("extraction")
            self.stage.progress.setValue(18)
        elif mode == "export":
            self.stage.set_progress(97)
        elif mode == "idle":
            self.stage.set_mode("idle")
            self.stage.progress.setValue(0)
        else:
            self.stage.set_progress(56)

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget#Root {
                background: #f6f7f9;
                color: #111827;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
                font-size: 10pt;
            }
            QWidget#Splash {
                background: #0b1220;
                border-radius: 18px;
            }
            QLabel#SplashTitle {
                color: #f8fafc;
                font-size: 26pt;
                font-weight: 760;
            }
            QLabel#SplashSubtitle {
                color: #94a3b8;
                font-size: 11pt;
            }
            QWidget#TopBar {
                background: #ffffff;
                border-bottom: 1px solid #e5e7eb;
            }
            QWidget#BottomBar {
                background: #ffffff;
                border-top: 1px solid #e5e7eb;
            }
            QLabel#Brand {
                font-size: 18pt;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#PanelTitle {
                font-size: 13pt;
                font-weight: 650;
                color: #111827;
            }
            QLabel#DialogTitle {
                font-size: 12pt;
                font-weight: 700;
                color: #111827;
            }
            QLabel#MutedLabel, QLabel#StageSubtitle, QLabel#HeroSubtitle {
                color: #6b7280;
            }
            QLabel#SectionTitle {
                color: #64748b;
                font-size: 8.5pt;
                font-weight: 700;
                letter-spacing: 0px;
            }
            QFrame#SectionLine {
                color: #d9dee8;
                background: #d9dee8;
                max-height: 1px;
            }
            QToolButton, QPushButton {
                background: #ffffff;
                border: 1px solid #d8dee8;
                border-radius: 11px;
                padding: 8px 13px;
                color: #111827;
            }
            QToolButton:hover, QPushButton:hover {
                background: #eef6ff;
                border-color: #9cc7ff;
            }
            QPushButton#PrimaryButton {
                background: #2563eb;
                border-color: #2563eb;
                color: #ffffff;
                font-weight: 650;
            }
            QPushButton#BottomRunButton {
                background: #2563eb;
                border-color: #2563eb;
                border-radius: 16px;
                color: #ffffff;
                font-weight: 700;
                min-width: 108px;
                padding: 8px 20px;
            }
            QPushButton#BottomRunButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
            QPushButton#BottomRunButton[running="true"] {
                background: #dc2626;
                border-color: #dc2626;
            }
            QPushButton#BottomRunButton[running="true"]:hover {
                background: #b91c1c;
                border-color: #b91c1c;
            }
            QToolButton#AddMaterialButton {
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                border-radius: 8px;
            }
            QToolButton#CollapseHeader {
                background: #ffffff;
                border: 1px solid #d8dee8;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 650;
                text-align: left;
            }
            QToolButton#CollapseHeader:checked {
                background: #eef6ff;
                border-color: #9cc7ff;
                color: #0f172a;
            }
            QWidget#BackendSwitch {
                background: #ffffff;
                border: 1px solid #cfd6e2;
                border-radius: 10px;
            }
            QPushButton#BackendOption {
                background: transparent;
                border: 0;
                border-radius: 8px;
                color: #475569;
                font-weight: 650;
                min-height: 28px;
                padding: 4px 10px;
            }
            QPushButton#BackendOption[selected="true"] {
                color: #0f172a;
            }
            QWidget#PluginSection:disabled, QToolButton#CollapseHeader:disabled, QTextEdit#PluginLog:disabled {
                color: #94a3b8;
            }
            QPushButton#PluginRunButton {
                background: #0f172a;
                border-color: #0f172a;
                color: #ffffff;
                font-weight: 650;
            }
            QPushButton#PluginRunButton:disabled {
                background: #e2e8f0;
                border-color: #cbd5e1;
                color: #94a3b8;
            }
            QProgressBar#InlineLoading {
                background: #e5e7eb;
                border: 0;
                border-radius: 5px;
                height: 8px;
            }
            QToolButton#TypeCard {
                min-width: 92px;
                min-height: 82px;
                border-radius: 8px;
                padding: 10px;
                font-weight: 650;
            }
            QToolButton#TypeCard:checked {
                background: #dbeafe;
                border-color: #2563eb;
                color: #0f172a;
            }
            QWidget#TrackRow {
                background: #ffffff;
            }
            QLabel#TrackName {
                color: #111827;
                font-weight: 600;
            }
            QToolButton#IconButton {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                border-radius: 6px;
            }
            QToolButton#DeleteIconButton {
                background: #dc2626;
                border-color: #dc2626;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                border-radius: 6px;
            }
            QToolButton#DeleteIconButton:hover {
                background: #b91c1c;
                border-color: #b91c1c;
            }
            QLabel#CountCapsule {
                color: #1e3a8a;
                background: #dbeafe;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 3px 7px;
                font-size: 8.5pt;
                font-weight: 650;
            }
            QToolButton#RunButton {
                background: #2563eb;
                border-color: #2563eb;
                color: #ffffff;
                font-weight: 650;
            }
            QToolButton#DensifyButton {
                background: #0f172a;
                border-color: #0f172a;
                color: #ffffff;
                font-weight: 650;
            }
            QToolButton#RunButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
            QScrollArea#InspectorScroll {
                background: #f8fafc;
                border: 0;
                border-right: 1px solid #d9dee8;
            }
            QWidget#ControlsPane {
                background: #f8fafc;
            }
            QListWidget#TrackList {
                background: #ffffff;
                border: 1px solid #d9dee8;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget#TrackList::item {
                padding: 10px;
                border-radius: 6px;
            }
            QListWidget#TrackList::item:selected {
                background: #dbeafe;
                color: #0f172a;
            }
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                background: #ffffff;
                border: 1px solid #cfd6e2;
                border-radius: 10px;
                min-height: 30px;
                padding: 4px 9px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
                border-color: #2563eb;
            }
            QWidget#StageCanvas {
                background: #080d16;
            }
            QWidget#StageHeader, QWidget#StageFooter, QWidget#StageView {
                background: #080d16;
                color: #e5edf7;
            }
            QLabel#StageTitle {
                color: #f8fafc;
                font-size: 15pt;
                font-weight: 700;
            }
            QLabel#StageBadge {
                color: #bfdbfe;
                background: #10223c;
                border: 1px solid #1f3b63;
                border-radius: 7px;
                padding: 5px 9px;
                font-weight: 700;
            }
            QLabel#HeroTitle {
                color: #f8fafc;
                font-size: 24pt;
                font-weight: 700;
            }
            QLabel#StageMetric {
                color: #cbd5e1;
                background: #0d1626;
                border: 1px solid #1f2937;
                border-radius: 7px;
                padding: 7px 10px;
            }
            QFrame#StageDivider {
                background: #1f2937;
                min-width: 1px;
                max-width: 1px;
            }
            QTextEdit#WorkbenchLog {
                background: #0b1220;
                color: #cbd5e1;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #1d4ed8;
            }
            QTextEdit#PluginLog {
                background: #0b1220;
                color: #cbd5e1;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 7px;
                selection-background-color: #1d4ed8;
            }
            QProgressBar {
                background: #121b2d;
                border: 0;
                border-radius: 6px;
                height: 10px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background: #22c55e;
                border-radius: 6px;
            }
            QCheckBox#DenseCompareSwitch {
                color: #cbd5e1;
                spacing: 7px;
            }
            QCheckBox#DenseCompareSwitch:disabled {
                color: #64748b;
            }
            QWebEngineView#ViserView, QLabel#ViewerPlaceholder {
                color: #cbd5e1;
                background: #0d1626;
                border: 1px solid #1f2937;
                border-radius: 8px;
            }
            QSplitter::handle {
                background: #d9dee8;
            }
            QSplitter::handle:hover {
                background: #9cc7ff;
            }
            """
        )


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--screenshot")
    parser.add_argument("--demo-state", choices=["idle", "extraction", "alignment", "export"], default="alignment")
    parser.add_argument("--demo-compare", action="store_true")
    parser.add_argument("--self-test-imports")
    args, _unknown = parser.parse_known_args(sys.argv[1:] if argv is None else argv)

    if args.self_test_imports:
        from app import write_runtime_import_report

        report = write_runtime_import_report(args.self_test_imports)
        return 0 if report["ok"] else 1

    qt_argv = [sys.argv[0]]
    app = QApplication(qt_argv)
    install_application_font(app)
    window = WorkbenchWindow()
    if args.screenshot or args.demo_state != "alignment":
        window.populate_demo(args.demo_state)
    if args.demo_compare and hasattr(window.stage, "compare_dense"):
        window.stage.compare_dense.setChecked(True)
    if args.screenshot:
        window.show()
        screenshot_path = Path(args.screenshot)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        def save_and_quit():
            window.grab().save(str(screenshot_path))
            app.quit()

        QTimer.singleShot(500, save_and_quit)
    elif args.self_test:
        window.show()
        QTimer.singleShot(250, app.quit)
    else:
        splash = SplashScreen()
        splash.show()

        def show_main_window():
            splash.close()
            window.show()

        QTimer.singleShot(820, show_main_window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
