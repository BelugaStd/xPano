import sys
from pathlib import Path

from xpano_workbench import __version__
from xpano_workbench.models import (
    AERIAL_PHOTOS,
    ORDINARY_VIDEO,
    PANORAMA_VIDEO,
    STANDARD_PHOTOS,
    ExtractionSettings,
    WorkbenchTrack,
    create_track,
)


try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QPushButton,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QStatusBar,
        QToolBar,
        QVBoxLayout,
        QWidget,
        QDoubleSpinBox,
        QSpinBox,
        QStyle,
    )
except ImportError as exc:  # pragma: no cover - covered by runtime smoke after PySide6 install.
    raise SystemExit(
        "PySide6 is required for the new xPano Workbench. "
        "Install requirements.txt or run the portable release build."
    ) from exc


class TrackListItem(QListWidgetItem):
    def __init__(self, track: WorkbenchTrack):
        super().__init__(f"{track.label}\n{track.display_type}")
        self.track_id = track.track_id


class InspectorPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._track = None
        self.setObjectName("InspectorPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Track Inspector")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.type_label = QLabel("No track selected")
        self.type_label.setObjectName("MutedLabel")
        layout.addWidget(self.type_label)

        form_frame = QFrame()
        form_frame.setObjectName("PanelCard")
        form = QFormLayout(form_frame)
        form.setContentsMargins(14, 14, 14, 14)
        form.setSpacing(10)

        self.spf = QDoubleSpinBox()
        self.spf.setRange(0.01, 9999.0)
        self.spf.setDecimals(2)
        self.spf.setSingleStep(0.25)
        form.addRow("Seconds / frame", self.spf)

        self.max_frames = QSpinBox()
        self.max_frames.setRange(0, 1_000_000)
        form.addRow("Max frames", self.max_frames)

        self.start_time = QDoubleSpinBox()
        self.start_time.setRange(0.0, 1_000_000.0)
        self.start_time.setSuffix(" s")
        form.addRow("Start time", self.start_time)

        self.end_time = QDoubleSpinBox()
        self.end_time.setRange(0.0, 1_000_000.0)
        self.end_time.setSuffix(" s")
        form.addRow("End time", self.end_time)

        self.metashape_enabled = QCheckBox("Use in Metashape")
        self.colmap_enabled = QCheckBox("Use in COLMAP")
        form.addRow(self.metashape_enabled)
        form.addRow(self.colmap_enabled)

        layout.addWidget(form_frame)
        layout.addStretch(1)

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
            self.type_label.setText("No track selected")
            return
        self.type_label.setText(f"{track.display_type} · {Path(track.paths[0]).name}")
        self.spf.setValue(track.extraction.seconds_per_frame)
        self.max_frames.setValue(track.extraction.max_frames)
        self.start_time.setValue(track.extraction.start_time_seconds)
        self.end_time.setValue(track.extraction.end_time_seconds)
        self.metashape_enabled.setChecked(track.enabled_for_metashape)
        self.colmap_enabled.setChecked(track.enabled_for_colmap)


class PreviewStage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("PreviewStage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Extraction Preview")
        title.setObjectName("StageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.stage_mode = QComboBox()
        self.stage_mode.addItems(["Extraction", "Alignment", "Output"])
        header.addWidget(self.stage_mode)
        layout.addLayout(header)

        preview_row = QHBoxLayout()
        self.left_preview = self._preview_card("Left fisheye")
        self.right_preview = self._preview_card("Right fisheye")
        preview_row.addWidget(self.left_preview)
        preview_row.addWidget(self.right_preview)
        layout.addLayout(preview_row, 2)

        self.viewer = QLabel("COLMAP camera and point cloud viewport will attach here")
        self.viewer.setObjectName("PointCloudViewport")
        self.viewer.setAlignment(Qt.AlignCenter)
        self.viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.viewer, 3)

    def _preview_card(self, text):
        card = QLabel(text)
        card.setAlignment(Qt.AlignCenter)
        card.setObjectName("PreviewCard")
        card.setMinimumHeight(180)
        return card


class WorkbenchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tracks: list[WorkbenchTrack] = []
        self.setWindowTitle(f"xPano Workbench {__version__}")
        self.resize(1320, 820)
        self.setMinimumSize(1040, 680)
        self._build_actions()
        self._build_layout()
        self._apply_style()

    def _build_actions(self):
        style = self.style()
        self.import_pano_action = QAction(style.standardIcon(QStyle.SP_DialogOpenButton), "Panorama video", self)
        self.import_pano_action.triggered.connect(self.add_panorama_track)
        self.import_ordinary_action = QAction(style.standardIcon(QStyle.SP_FileIcon), "Ordinary video", self)
        self.import_ordinary_action.triggered.connect(self.add_ordinary_video_track)
        self.import_photos_action = QAction(style.standardIcon(QStyle.SP_DirOpenIcon), "Photo folder", self)
        self.import_photos_action.triggered.connect(self.add_photo_track)

        self.environment_action = QAction(style.standardIcon(QStyle.SP_ComputerIcon), "Environment", self)
        self.run_action = QAction(style.standardIcon(QStyle.SP_MediaPlay), "Run", self)
        self.pause_action = QAction(style.standardIcon(QStyle.SP_MediaPause), "Pause", self)
        self.stop_action = QAction(style.standardIcon(QStyle.SP_MediaStop), "Stop", self)
        self.output_action = QAction(style.standardIcon(QStyle.SP_DirLinkIcon), "Open output", self)

        toolbar = QToolBar("Command Bar")
        toolbar.setObjectName("CommandBar")
        toolbar.setMovable(False)
        toolbar.addAction(self.import_pano_action)
        toolbar.addAction(self.import_ordinary_action)
        toolbar.addAction(self.import_photos_action)
        toolbar.addSeparator()
        toolbar.addAction(self.environment_action)
        toolbar.addAction(self.run_action)
        toolbar.addAction(self.pause_action)
        toolbar.addAction(self.stop_action)
        toolbar.addSeparator()
        toolbar.addAction(self.output_action)
        self.addToolBar(toolbar)

        self.import_menu = self.menuBar().addMenu("Import")
        self.import_menu.addAction(self.import_pano_action)
        self.import_menu.addAction(self.import_ordinary_action)
        self.import_menu.addAction(self.import_photos_action)

    def _build_layout(self):
        root_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(root_splitter)

        left_workspace = QSplitter(Qt.Horizontal)
        left_workspace.setObjectName("LeftWorkspace")

        self.workflow_list = QListWidget()
        self.workflow_list.setObjectName("WorkflowRail")
        self.workflow_list.addItems(["Material", "Extract", "Align", "Densify", "Export", "Log"])
        self.workflow_list.setFixedWidth(116)
        left_workspace.addWidget(self.workflow_list)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(14, 14, 14, 14)
        controls_layout.setSpacing(12)

        track_header = QHBoxLayout()
        title = QLabel("Tracks")
        title.setObjectName("PanelTitle")
        track_header.addWidget(title)
        track_header.addStretch(1)
        add_button = QPushButton("Add")
        add_button.setMenu(self.import_menu)
        track_header.addWidget(add_button)
        controls_layout.addLayout(track_header)

        self.track_list = QListWidget()
        self.track_list.setObjectName("TrackList")
        self.track_list.currentItemChanged.connect(self._on_track_selected)
        controls_layout.addWidget(self.track_list, 2)

        self.inspector = InspectorPanel()
        controls_layout.addWidget(self.inspector, 3)
        left_workspace.addWidget(controls)
        left_workspace.setSizes([116, 360])

        self.stage_stack = QStackedWidget()
        self.stage_stack.addWidget(PreviewStage())

        root_splitter.addWidget(left_workspace)
        root_splitter.addWidget(self.stage_stack)
        root_splitter.setSizes([500, 820])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _next_index(self):
        return len(self.tracks) + 1

    def _append_track(self, track: WorkbenchTrack):
        self.tracks.append(track)
        item = TrackListItem(track)
        self.track_list.addItem(item)
        self.track_list.setCurrentItem(item)
        self.statusBar().showMessage(f"Added {track.display_type}: {track.label}", 5000)

    def add_panorama_track(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add panorama video",
            "",
            "Panorama video (*.osv *.insv *.mp4);;All files (*.*)",
        )
        for path in paths:
            video = Path(path)
            self._append_track(create_track(self._next_index(), PANORAMA_VIDEO, video.stem, [video]))

    def add_ordinary_video_track(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add ordinary video",
            "",
            "Video files (*.mp4 *.mov *.avi *.mkv);;All files (*.*)",
        )
        for path in paths:
            video = Path(path)
            self._append_track(create_track(self._next_index(), ORDINARY_VIDEO, video.stem, [video]))

    def add_photo_track(self):
        path = QFileDialog.getExistingDirectory(self, "Add photo folder")
        if path:
            folder = Path(path)
            self._append_track(create_track(self._next_index(), STANDARD_PHOTOS, folder.name, [folder]))

    def _on_track_selected(self, current, _previous):
        if not current:
            self.inspector.set_track(None)
            return
        track = next((item for item in self.tracks if item.track_id == current.track_id), None)
        self.inspector.set_track(track)

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f3f4f7;
                color: #17202c;
                font-family: "Segoe UI";
                font-size: 10.5pt;
            }
            QMenuBar, QToolBar#CommandBar {
                background: #fbfbfd;
                border-bottom: 1px solid #d7dbe3;
                spacing: 8px;
            }
            QToolButton, QPushButton {
                background: #ffffff;
                border: 1px solid #d7dbe3;
                border-radius: 10px;
                padding: 7px 12px;
            }
            QToolButton:hover, QPushButton:hover {
                background: #eef5ff;
                border-color: #9fc6ff;
            }
            QListWidget#WorkflowRail {
                background: #e9ecf2;
                border: 0;
                padding: 10px;
            }
            QListWidget#TrackList, QFrame#PanelCard {
                background: #ffffff;
                border: 1px solid #d9dde6;
                border-radius: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 10px;
            }
            QListWidget::item:selected {
                background: #dbeafe;
                color: #0f172a;
            }
            QLabel#PanelTitle, QLabel#StageTitle {
                font-size: 14pt;
                font-weight: 650;
            }
            QLabel#MutedLabel {
                color: #64748b;
            }
            QLabel#PreviewCard, QLabel#PointCloudViewport {
                background: #111827;
                color: #dbeafe;
                border-radius: 16px;
                border: 1px solid #273449;
            }
            QSplitter::handle {
                background: #d8dde7;
            }
            QSplitter::handle:hover {
                background: #9fc6ff;
            }
            """
        )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    self_test = "--self-test" in argv
    qt_argv = [sys.argv[0], *(arg for arg in argv if arg != "--self-test")]
    app = QApplication(qt_argv)
    window = WorkbenchWindow()
    window.show()
    if self_test:
        QTimer.singleShot(250, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
