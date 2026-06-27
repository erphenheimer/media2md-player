"""media2md-player GUI 主窗口 — 视频播放器 + 文稿面板（现代化翻新）。"""

import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")

from PyQt6.QtCore import Qt, QUrl, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QFont, QColor, QTextCursor
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTextEdit,
    QPushButton,
    QSlider,
    QLabel,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QStatusBar,
    QFormLayout,
    QComboBox,
    QGroupBox,
    QLineEdit,
    QScrollArea,
)

from media2md.models.transcript import Transcript, SourceType
from media2md.pipeline.extractor import extract_transcript
from media2md.pipeline.transcriber import transcribe_file, resolve_whisper
from media2md.pipeline.corrector import correct_transcript, CorrectionResult
from media2md.pipeline.guide_generator import generate_guide
from media2md.pipeline.exporter import (
    export_transcript,
    export_guide,
    generate_output_paths,
)
from media2md.utils.config import (
    load_env,
    get_api_config,
    get_whisper_config,
    config_list,
    config_set,
)


# ========================================================================
# 全局 QSS 暗色主题
# ========================================================================

DARK_THEME_QSS = """
/* ---- 全局 ---- */
QMainWindow, QWidget, QDialog {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
}

/* ---- 菜单栏 ---- */
QMenuBar {
    background-color: #252525;
    color: #cccccc;
    border-bottom: 1px solid #333333;
    padding: 2px 0;
}
QMenuBar::item {
    padding: 4px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #333333;
    color: #ffffff;
}

QMenu {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 28px 6px 16px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #2196F3;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #444444;
    margin: 4px 8px;
}

/* ---- 按钮 ---- */
QPushButton {
    background-color: #333333;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #444444;
    border-color: #2196F3;
}
QPushButton:pressed {
    background-color: #1976D2;
}
QPushButton:disabled {
    background-color: #2a2a2a;
    color: #666666;
    border-color: #3a3a3a;
}
QPushButton:checked {
    background-color: #2196F3;
    border-color: #1976D2;
}

/* ---- 侧边栏按钮 ---- */
QPushButton#sidebar_btn {
    background-color: transparent;
    border: none;
    border-radius: 0;
    padding: 10px 0;
    font-size: 20px;
    min-height: 44px;
    color: #888888;
}
QPushButton#sidebar_btn:hover {
    background-color: #333333;
    color: #ffffff;
}
QPushButton#sidebar_btn:checked {
    background-color: #2196F3;
    color: #ffffff;
    border-left: 3px solid #64B5F6;
}

/* ---- 操作按钮（转写/修正/导读/导出） ---- */
QPushButton#action_btn {
    background-color: #2a2a2a;
    border: 1px solid #444444;
    border-radius: 6px;
    padding: 4px 4px;
    font-size: 16px;
    font-weight: bold;
    min-width: 36px;
    min-height: 28px;
}
QPushButton#action_btn:hover {
    background-color: #3a3a3a;
    border-color: #2196F3;
}
QPushButton#action_btn:pressed {
    background-color: #1976D2;
}
QPushButton#action_btn:disabled {
    background-color: #222222;
    color: #555555;
    border-color: #333333;
}

/* ---- 滑块 ---- */
QSlider::groove:horizontal {
    background: #444444;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #2196F3;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #42A5F5;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}
QSlider::sub-page:horizontal {
    background: #2196F3;
    border-radius: 2px;
}

/* ---- 文本框 ---- */
QTextEdit {
    background-color: #1a1a1a;
    color: #dddddd;
    border: 1px solid #444444;
    border-radius: 6px;
    padding: 10px;
    font-size: 14px;
    selection-background-color: #2196F3;
    selection-color: #ffffff;
}

/* ---- 标签页 ---- */
QTabWidget::pane {
    background-color: #1e1e1e;
    border: 1px solid #444444;
    border-radius: 0 0 6px 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: #2d2d2d;
    color: #888888;
    padding: 8px 20px;
    border: 1px solid #444444;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #ffffff;
    border-bottom: 2px solid #2196F3;
}
QTabBar::tab:hover {
    background-color: #3a3a3a;
    color: #ffffff;
}

/* ---- 下拉框 ---- */
QComboBox {
    background-color: #333333;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 120px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #2196F3;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
    subcontrol-origin: padding;
    subcontrol-position: top right;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #888888;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #333333;
    color: #ffffff;
    selection-background-color: #2196F3;
    border: 1px solid #555555;
    border-radius: 4px;
    outline: none;
}

/* ---- 分组框 ---- */
QGroupBox {
    background-color: #252525;
    border: 1px solid #444444;
    border-radius: 8px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #2196F3;
}

/* ---- 标签 ---- */
QLabel {
    color: #cccccc;
    background: transparent;
}

/* ---- 状态栏 ---- */
QStatusBar {
    background-color: #252525;
    color: #888888;
    border-top: 1px solid #333333;
    padding: 2px 8px;
    font-size: 12px;
}
QStatusBar::item {
    border: none;
}

/* ---- 滚动条 ---- */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #555555;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #777777;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #555555;
    min-width: 30px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #777777;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""


# ========================================================================
# 后台工作者：在 QThread 中执行耗时操作，通过信号返回结果
# ========================================================================

class Worker(QObject):
    """在单独线程中执行耗时操作，不阻塞 GUI。"""

    finished = pyqtSignal(object)   # 成功时返回结果
    error = pyqtSignal(str)         # 失败时返回错误信息
    progress = pyqtSignal(str)      # 进度更新

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")


# ========================================================================
# 文稿高亮跟踪
# ========================================================================

class TranscriptHighlighter:
    """文稿高亮跟踪器 — 根据播放位置高亮对应段落。"""

    def __init__(self, text_edit: QTextEdit):
        self.text_edit = text_edit
        self.segments: list[dict] = []
        self.current_index = -1

    def set_transcript(self, transcript: Transcript):
        self.segments = []
        self.current_index = -1
        doc = self.text_edit.document()
        for seg in transcript.segments:
            ts_line = seg.to_markdown_line()
            cursor = doc.find(ts_line)
            if cursor:
                self.segments.append({
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                    "block_start": cursor.position(),
                    "block_end": cursor.position() + len(ts_line),
                })

    def update_position(self, position_ms: int):
        new_index = -1
        for i, seg in enumerate(self.segments):
            if seg["start_ms"] <= position_ms <= seg["end_ms"]:
                new_index = i
                break

        if new_index == self.current_index:
            return

        if self.current_index >= 0:
            old_seg = self.segments[self.current_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(old_seg["block_start"])
            cursor.setPosition(old_seg["block_end"], QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
            fmt.setBackground(QColor("transparent"))
            cursor.setCharFormat(fmt)

        if new_index >= 0:
            new_seg = self.segments[new_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(new_seg["block_start"])
            cursor.setPosition(new_seg["block_end"], QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
            fmt.setBackground(QColor("#FFFF00"))
            cursor.setCharFormat(fmt)
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

        self.current_index = new_index


# ========================================================================
# 主窗口
# ========================================================================

class Media2MDWindow(QMainWindow):
    """主窗口 — 现代化暗色主题，侧边栏导航 + 标签式内容面板。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("media2md-player")
        self.resize(1200, 700)

        # 应用全局主题样式
        self.setStyleSheet(DARK_THEME_QSS)

        self.current_file: Path | None = None
        self.transcript: Transcript | None = None
        self.raw_transcript: Transcript | None = None
        self.corrected_transcript: Transcript | None = None
        self.guide_md: str | None = None
        self.config = load_env()
        self.api_config = get_api_config(self.config)

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)

        # 后台线程管理
        self._worker_thread: QThread | None = None
        self._worker: Worker | None = None

        self._build_menu()
        self._build_central()
        self._build_statusbar()

        self._position_timer = QTimer(self)
        self._position_timer.setInterval(200)
        self._position_timer.timeout.connect(self._on_position_changed)

    # ========== 任务管理 ==========

    def _start_task(self, fn, *args, **kwargs):
        """在后台线程中启动一个耗时任务，期间禁用所有操作按钮。"""
        self._set_buttons_enabled(False)
        self.status_bar.showMessage("处理中...")

        self._worker_thread = QThread(self)
        self._worker = Worker(fn, *args, **kwargs)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_task_finished)
        self._worker.error.connect(self._on_task_error)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        self._worker_thread.start()

    def _set_buttons_enabled(self, enabled: bool):
        for btn in [self.btn_transcribe, self.btn_correct, self.btn_guide, self.btn_export]:
            btn.setEnabled(enabled)

    def _on_task_finished(self, result):
        """后台任务成功完成 — 由子类重写具体行为。"""
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
        self._worker_thread = None
        self._worker = None
        self._set_buttons_enabled(True)

    def _on_task_error(self, message: str):
        """后台任务失败。"""
        self._worker_thread.quit()
        self._worker_thread.wait()
        self._worker_thread = None
        self._worker = None
        self._set_buttons_enabled(True)
        QMessageBox.critical(self, "操作失败", message)
        self.status_bar.showMessage("操作失败")

    # ========== UI 构建 ==========

    def _build_menu(self):
        menubar = self.menuBar()
        # ---- 文件菜单 ----
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QAction("打开文件(&O)...", self)
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)
        export_action = QAction("导出 Markdown(&E)...", self)
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ---- 处理菜单 ----
        process_menu = menubar.addMenu("处理(&P)")
        correct_action = QAction("AI 文稿修正(&C)", self)
        correct_action.triggered.connect(self._on_correct)
        process_menu.addAction(correct_action)
        guide_action = QAction("生成导读(&G)", self)
        guide_action.triggered.connect(self._on_generate_guide)
        process_menu.addAction(guide_action)

        # ---- 设置菜单 ----
        settings_menu = menubar.addMenu("设置(&S)")
        setup_action = QAction("初始化环境(&I)...", self)
        setup_action.triggered.connect(self._on_setup)
        settings_menu.addAction(setup_action)
        pref_action = QAction("Whisper 参数(&P)...", self)
        pref_action.triggered.connect(self._on_settings)
        settings_menu.addAction(pref_action)

    def _build_central(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- 左侧边栏 ----
        self._build_sidebar(main_layout)

        # ---- 右侧主面板 ----
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        # 视频区域 + 标签内容上下分栏
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #444444; border-radius: 2px; }"
        )

        # ---- 上半：视频播放器 ----
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(6)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(320, 180)
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        video_layout.addWidget(self.video_widget)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        # 播放控制栏
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.play_btn = QPushButton("\u25b6")
        self.play_btn.setFixedSize(38, 32)
        self.play_btn.setStyleSheet(
            "QPushButton { font-size: 16px; padding: 0; border-radius: 16px; }"
        )
        self.play_btn.clicked.connect(self._on_play_pause)
        controls.addWidget(self.play_btn)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(0)
        self.position_slider.sliderMoved.connect(self._on_seek)
        controls.addWidget(self.position_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #888888; font-size: 12px; min-width: 100px;")
        controls.addWidget(self.time_label)

        video_layout.addLayout(controls)

        # 打开文件按钮（视频未加载时显示）
        self.load_btn = QPushButton("\U0001f4c2 打开文件...")
        self.load_btn.setToolTip("支持: mp4/mkv/mov/avi/mp3/wav 及 srt/vtt/ass 字幕文件")
        self.load_btn.setObjectName("action_btn")
        self.load_btn.clicked.connect(self._on_open_file)
        video_layout.addWidget(self.load_btn)

        splitter.addWidget(video_container)

        # ---- 下半：操作按钮 + 标签页 ----
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        # 操作按钮栏（图标 + tooltip）
        action_bar = QHBoxLayout()
        action_bar.setSpacing(6)

        self.btn_transcribe = QPushButton("\U0001f399\ufe0f 语音转写")
        self.btn_transcribe.setToolTip("使用 Whisper 自动语音识别提取文稿")
        self.btn_transcribe.setObjectName("action_btn")
        self.btn_transcribe.setFixedWidth(110)
        self.btn_transcribe.clicked.connect(self._on_transcribe)

        self.btn_correct = QPushButton("\u270f\ufe0f AI 修正")
        self.btn_correct.setToolTip("调用 AI API 修正转写错误（仅 Whisper 转写需此步骤）")
        self.btn_correct.setObjectName("action_btn")
        self.btn_correct.setFixedWidth(110)
        self.btn_correct.clicked.connect(self._on_correct)

        self.btn_guide = QPushButton("\U0001f4d6 生成导读")
        self.btn_guide.setToolTip("由 AI 自动生成结构化阅读指南")
        self.btn_guide.setObjectName("action_btn")
        self.btn_guide.setFixedWidth(110)
        self.btn_guide.clicked.connect(self._on_generate_guide)

        self.btn_export = QPushButton("\U0001f4be 导出文稿")
        self.btn_export.setToolTip("将当前文稿导出为 Markdown 文件")
        self.btn_export.setObjectName("action_btn")
        self.btn_export.setFixedWidth(110)
        self.btn_export.clicked.connect(self._on_export)

        for btn in [self.btn_transcribe, self.btn_correct, self.btn_guide, self.btn_export]:
            action_bar.addWidget(btn)
        action_bar.addStretch()
        bottom_layout.addLayout(action_bar)

        # 标签页
        self.tab_widget = QTabWidget()

        # ---- Tab 0: 文稿 ----
        self.transcript_tab = QWidget()
        tab0_layout = QVBoxLayout(self.transcript_tab)
        tab0_layout.setContentsMargins(0, 0, 0, 0)
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setReadOnly(True)
        self.transcript_edit.setFont(QFont("Microsoft YaHei", 10))
        tab0_layout.addWidget(self.transcript_edit)
        self.tab_widget.addTab(self.transcript_tab, "文稿")

        # ---- Tab 1: 修正版 ----
        self.corrected_tab = QWidget()
        tab1_layout = QVBoxLayout(self.corrected_tab)
        tab1_layout.setContentsMargins(0, 0, 0, 0)
        self.corrected_edit = QTextEdit()
        self.corrected_edit.setReadOnly(True)
        self.corrected_edit.setFont(QFont("Microsoft YaHei", 10))
        tab1_layout.addWidget(self.corrected_edit)
        self.tab_widget.addTab(self.corrected_tab, "修正版")

        # ---- Tab 2: 导读 ----
        self.guide_tab = QWidget()
        tab2_layout = QVBoxLayout(self.guide_tab)
        tab2_layout.setContentsMargins(0, 0, 0, 0)
        self.guide_edit = QTextEdit()
        self.guide_edit.setReadOnly(True)
        self.guide_edit.setFont(QFont("Microsoft YaHei", 10))
        tab2_layout.addWidget(self.guide_edit)
        self.tab_widget.addTab(self.guide_tab, "导读")

        # ---- Tab 3: 设置（可滚动） ----
        self.settings_tab = QWidget()
        self._build_settings_form()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.settings_tab)
        self.tab_widget.addTab(scroll, "设置")

        bottom_layout.addWidget(self.tab_widget)
        splitter.addWidget(bottom_panel)

        # 初始比例：视频 35%，内容 65%
        splitter.setSizes([220, 580])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)

        right_layout.addWidget(splitter)
        main_layout.addWidget(right_panel)
        self.setCentralWidget(central)

        # 高亮跟踪器（关联到文稿标签页的文本框）
        self.highlighter = TranscriptHighlighter(self.transcript_edit)

    def _build_sidebar(self, parent_layout):
        """构建左侧导航栏。"""
        sidebar = QWidget()
        sidebar.setFixedWidth(60)
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(
            "QWidget#sidebar { background-color: #252525; border-right: 1px solid #333333; }"
        )

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 8, 4, 8)
        sidebar_layout.setSpacing(4)

        # 按钮配置：(图标, 提示文本, 回调, 参数)
        btn_configs = [
            ("\U0001f4c1", "打开文件", self._on_open_file, None),
            ("\U0001f4dd", "文稿", self._on_sidebar_switch_tab, 0),
            ("\u270f\ufe0f", "修正版", self._on_sidebar_switch_tab, 1),
            ("\U0001f4d6", "导读", self._on_sidebar_switch_tab, 2),
            ("\u2699\ufe0f", "设置", self._on_sidebar_switch_tab, 3),
        ]

        self.side_buttons = []
        for i, (icon, tip, callback, arg) in enumerate(btn_configs):
            btn = QPushButton(icon)
            btn.setObjectName("sidebar_btn")
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if arg is not None:
                btn.clicked.connect(lambda checked, idx=arg: callback(idx))
            else:
                btn.clicked.connect(callback)
            sidebar_layout.addWidget(btn)
            self.side_buttons.append(btn)

        sidebar_layout.addStretch()
        parent_layout.addWidget(sidebar)

        # 默认选中第二个（文稿）
        if len(self.side_buttons) > 1:
            self.side_buttons[1].setChecked(True)

    def _on_sidebar_switch_tab(self, index: int):
        """侧边栏按钮切换标签页。"""
        for i, btn in enumerate(self.side_buttons):
            btn.setChecked(i == index + 1)
        self.tab_widget.setCurrentIndex(index)

    def _build_settings_form(self):
        """构建设置标签页的表单。"""
        layout = QVBoxLayout(self.settings_tab)
        layout.setSpacing(24)
        layout.setContentsMargins(20, 20, 20, 20)

        # ---- Whisper 设置组 ----
        whisper_group = QGroupBox("Whisper 转写设置")
        whisper_form = QFormLayout(whisper_group)
        whisper_form.setSpacing(12)
        whisper_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        cfgs = {c["key"]: c for c in config_list()}

        # 模型大小
        self.model_combo = QComboBox()
        for m in ["tiny", "base", "small", "medium", "large"]:
            self.model_combo.addItem(m, m)
        self.model_combo.setCurrentText(cfgs.get("whisper.model", {}).get("value", "medium"))
        self.model_combo.currentTextChanged.connect(
            lambda t: config_set("whisper.model", t)
        )
        whisper_form.addRow("模型大小:", self.model_combo)

        # 设备
        self.device_combo = QComboBox()
        self.device_combo.addItems(["cuda", "cpu"])
        self.device_combo.setCurrentText(cfgs.get("whisper.device", {}).get("value", "cuda"))
        self.device_combo.currentTextChanged.connect(
            lambda t: config_set("whisper.device", t)
        )
        whisper_form.addRow("转写设备:", self.device_combo)

        # 计算精度
        self.compute_combo = QComboBox()
        self.compute_combo.addItems(["float16", "int8", "float32"])
        current = cfgs.get("whisper.compute_type", {}).get("value", "float16")
        self.compute_combo.setCurrentText(current)
        self.compute_combo.currentTextChanged.connect(
            lambda t: config_set("whisper.compute_type", t)
        )
        whisper_form.addRow("计算精度:", self.compute_combo)

        # 语言
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["zh", "en", "ja", "auto"])
        self.lang_combo.setCurrentText(cfgs.get("whisper.language", {}).get("value", "zh"))
        self.lang_combo.currentTextChanged.connect(
            lambda t: config_set("whisper.language", t)
        )
        whisper_form.addRow("语言:", self.lang_combo)

        layout.addWidget(whisper_group)

        # ---- API 配置组 ----
        api_group = QGroupBox("API 配置（AI 修正/导读）")
        api_form = QFormLayout(api_group)
        api_form.setSpacing(12)
        api_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # API 提供商
        self.api_provider_combo = QComboBox()
        self.api_provider_combo.addItems(["deepseek", "openai", "kimi", "custom"])
        self.api_provider_combo.setCurrentText(cfgs.get("api.provider", {}).get("value", "deepseek"))
        def _on_provider_change(provider):
            config_set("api.provider", provider)
            # Auto-fill URL and model based on provider
            presets = {
                "deepseek": ("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
                "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
                "kimi": ("https://api.moonshot.cn/v1/chat/completions", "moonshot-v1-8k"),
                "custom": ("", ""),
            }
            url, model = presets.get(provider, ("", ""))
            if url:
                self.api_url_input.setText(url)
                config_set("api.url", url)
            if model:
                self.api_model_input.setText(model)
                config_set("api.model", model)
        self.api_provider_combo.currentTextChanged.connect(_on_provider_change)
        api_form.addRow("提供商:", self.api_provider_combo)

        # API Key (password field with show/hide)
        key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        current_key = cfgs.get("api.key", {}).get("value", "")
        self.api_key_input.setText("********" if current_key and current_key != "your_api_key_here" else "")
        self.api_key_input.setPlaceholderText("输入 API Key")
        key_layout.addWidget(self.api_key_input)
        
        self.api_key_toggle = QPushButton("显示")
        self.api_key_toggle.setFixedWidth(50)
        self.api_key_toggle.setStyleSheet("QPushButton { font-size: 11px; padding: 2px 6px; }")
        def _toggle_key():
            if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
                self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
                self.api_key_toggle.setText("隐藏")
            else:
                self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
                self.api_key_toggle.setText("显示")
        self.api_key_toggle.clicked.connect(_toggle_key)
        key_layout.addWidget(self.api_key_toggle)
        
        api_form.addRow("API Key:", key_layout)

        # API URL
        self.api_url_input = QLineEdit()
        self.api_url_input.setText(cfgs.get("api.url", {}).get("value", "https://api.deepseek.com/v1/chat/completions"))
        self.api_url_input.setPlaceholderText("https://api.deepseek.com/v1/chat/completions")
        self.api_url_input.textChanged.connect(lambda t: config_set("api.url", t))
        api_form.addRow("API 地址:", self.api_url_input)

        # Model Name
        self.api_model_input = QLineEdit()
        self.api_model_input.setText(cfgs.get("api.model", {}).get("value", "deepseek-chat"))
        self.api_model_input.setPlaceholderText("deepseek-chat")
        self.api_model_input.textChanged.connect(lambda t: config_set("api.model", t))
        api_form.addRow("模型名:", self.api_model_input)

        # Test Connection button
        test_layout = QHBoxLayout()
        self.api_test_btn = QPushButton("测试连接")
        self.api_test_btn.setObjectName("action_btn")
        self.api_test_btn.setStyleSheet("QPushButton { background-color: #2E7D32; border-color: #388E3C; } QPushButton:hover { background-color: #388E3C; }")
        self.api_test_btn.clicked.connect(self._on_test_api)
        test_layout.addWidget(self.api_test_btn)
        
        self.api_test_status = QLabel("")
        self.api_test_status.setStyleSheet("color: #888888; font-style: italic; padding: 4px 0;")
        test_layout.addWidget(self.api_test_status, 1)
        api_form.addRow("", test_layout)

        layout.addWidget(api_group)

        # ---- 环境初始化组 ----
        setup_group = QGroupBox("环境初始化")
        setup_layout = QVBoxLayout(setup_group)
        setup_layout.setSpacing(10)

        self.setup_btn = QPushButton("\U0001f680 初始化转写环境")
        self.setup_btn.setObjectName("action_btn")
        self.setup_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; border-color: #1976D2; font-weight: bold; }"
            "QPushButton:hover { background-color: #1976D2; }"
            "QPushButton:pressed { background-color: #0D47A1; }"
        )
        self.setup_btn.clicked.connect(self._on_setup)
        setup_layout.addWidget(self.setup_btn)

        self.setup_status = QLabel("点击上方按钮检查并初始化 Whisper 转写环境")
        self.setup_status.setStyleSheet(
            "color: #888888; font-style: italic; padding: 4px 0;"
        )
        self.setup_status.setWordWrap(True)
        setup_layout.addWidget(self.setup_status)

        layout.addWidget(setup_group)
        layout.addStretch()

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    # ========== 事件处理 ==========

    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "媒体文件 (*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.m4a *.srt *.vtt *.ass);;所有文件 (*.*)",
        )
        if not path:
            return
        self.current_file = Path(path)
        self.setWindowTitle(f"media2md-player - {self.current_file.name}")
        self.status_bar.showMessage(f"已打开: {self.current_file.name}")
        self._load_transcript()
        if self.current_file.suffix.lower() in (
            ".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".wmv", ".m4v",
            ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
        ):
            self.player.setSource(QUrl.fromLocalFile(str(self.current_file)))
            self.load_btn.hide()
            self.play_btn.setEnabled(True)
            self._position_timer.start()
            # 切换到文稿标签页
            self.tab_widget.setCurrentIndex(0)
            self._on_sidebar_switch_tab(0)

    def _load_transcript(self):
        if not self.current_file:
            return
        self.raw_transcript = extract_transcript(self.current_file)
        if self.raw_transcript.segments:
            self.transcript = self.raw_transcript
            self.transcript_edit.setPlainText(self.raw_transcript.to_markdown())
            self.highlighter.set_transcript(self.raw_transcript)
            self.status_bar.showMessage(
                f"文稿已加载: {len(self.raw_transcript.segments)} 段落 "
                f"(来源: {self.raw_transcript.source_type.value})"
            )
        else:
            audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
            is_audio = self.current_file.suffix.lower() in audio_exts
            if is_audio:
                hint = "音频文件无内嵌字幕。\n\n点击「转写」按钮使用 Whisper 语音识别提取文稿。"
            else:
                hint = "未找到字幕。\n\n点击「转写」按钮使用 Whisper 语音识别。"
            self.transcript_edit.setPlainText(hint)
            self.corrected_edit.clear()
            self.guide_edit.clear()

    # ---- 转写 ----

    def _on_transcribe(self):
        if not self.current_file:
            QMessageBox.warning(self, "提示", "请先打开文件。")
            return

        # 检查 Whisper 是否可用
        wcfg = resolve_whisper()
        if not wcfg.get("exe"):
            reply = QMessageBox.question(
                self, "首次使用",
                "未检测到 Whisper 转写引擎。\n\n"
                "首次使用需要运行环境初始化：\n"
                "1. 安装 whisper-ctranslate2\n"
                "2. 下载语音识别模型 (~1.5GB)\n\n"
                "是否现在初始化？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_setup()
            return

        self.status_bar.showMessage("正在转写（后台运行，不影响操作）...")
        self._start_task(
            transcribe_file,
            self.current_file,
            process_dir=self.current_file.parent / ".process",
        )
        # 重连信号以处理转写结果
        self._worker.finished.connect(self._on_transcribe_done)

    def _on_transcribe_done(self, result):
        """转写完成后在主线程更新 UI。"""
        self.raw_transcript = result
        self.transcript = result
        md = result.to_markdown()
        self.transcript_edit.setPlainText(md)
        self.highlighter.set_transcript(result)
        self.status_bar.showMessage(
            f"转写完成: {len(result.segments)} 段落"
        )
        # 自动切换到「文稿」标签页
        self.tab_widget.setCurrentIndex(0)
        self._on_sidebar_switch_tab(0)

    # ---- AI 修正 ----

    def _on_correct(self):
        if not self.transcript or not self.transcript.segments:
            QMessageBox.warning(self, "提示", "请先加载文稿。")
            return
        if self.transcript.source_type in (SourceType.EXTERNAL_SUBTITLE, SourceType.EMBEDDED_SUBTITLE):
            QMessageBox.information(self, "提示", "字幕来源，无需修正。")
            return
        api_key = self.api_config.get("api_key", "")
        if not api_key or api_key == "your_api_key_here":
            QMessageBox.warning(self, "提示", "请在 .env 中配置 API_KEY。")
            return

        self.status_bar.showMessage("正在 AI 修正（后台运行）...")
        self._start_task(correct_transcript, self.transcript, api_config=self.api_config)
        self._worker.finished.connect(self._on_correct_done)

    def _on_correct_done(self, result: CorrectionResult):
        corrected = Transcript(
            segments=result.corrected_segments,
            source_type=self.transcript.source_type,
            source_path=self.transcript.source_path,
        )
        self.corrected_transcript = corrected
        self.transcript = corrected
        md = corrected.to_markdown()
        self.corrected_edit.setPlainText(md)
        self.status_bar.showMessage(
            f"修正完成: {len(result.logs)} 处修改, {len(result.review_needed)} 处待审核"
        )
        # 自动切换到「修正版」标签页
        self.tab_widget.setCurrentIndex(1)
        self._on_sidebar_switch_tab(1)

    # ---- 导读 ----

    def _on_generate_guide(self):
        if not self.transcript:
            QMessageBox.warning(self, "提示", "请先加载文稿。")
            return
        full_text = self.transcript.full_text
        if not full_text:
            QMessageBox.warning(self, "提示", "文稿为空，无法生成导读。")
            return
        api_key = self.api_config.get("api_key", "")
        if not api_key or api_key == "your_api_key_here":
            QMessageBox.warning(self, "提示", "请在 .env 中配置 API_KEY。")
            return

        self.status_bar.showMessage("正在生成导读（后台运行）...")
        self._start_task(
            generate_guide, full_text,
            title=self.current_file.stem if self.current_file else "",
            api_config=self.api_config,
        )
        self._worker.finished.connect(self._on_guide_done)

    def _on_guide_done(self, guide):
        guide_md = guide.to_markdown()
        self.guide_md = guide_md
        self.guide_edit.setPlainText(guide_md)
        self.status_bar.showMessage("导读生成完成")
        # 自动切换到「导读」标签页
        self.tab_widget.setCurrentIndex(2)
        self._on_sidebar_switch_tab(2)

    # ---- 导出 ----

    def _on_export(self):
        if not self.transcript:
            QMessageBox.warning(self, "提示", "没有可导出的内容。")
            return
        output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not output_dir:
            return
        stem = self.current_file.stem if self.current_file else "output"
        paths = generate_output_paths(stem, output_dir)
        export_transcript(self.transcript, paths["transcript"])
        self.status_bar.showMessage(f"导出完成: {paths['transcript']}")

    # ---- 设置 ----

    def _on_settings(self):
        """打开设置标签页。"""
        self.tab_widget.setCurrentIndex(3)
        self._on_sidebar_switch_tab(3)

    def _on_setup(self):
        """初始化环境。"""
        from media2md.pipeline.setup import check_env, run_setup as _run_setup

        env = check_env()
        if env.ready_to_transcribe:
            QMessageBox.information(self, "初始化", "环境已就绪，无需初始化。")
            self.setup_status.setText("\u2705 环境已就绪")
            self.setup_status.setStyleSheet("color: #4CAF50; font-style: normal;")
            return

        msg = "将执行以下步骤:\n"
        if not env.whisper_ok:
            msg += "  1. 安装 whisper-ctranslate2\n"
        if not env.model_exists:
            msg += "  2. 下载 Whisper 模型 (medium)\n"
        msg += "\n继续吗？"

        reply = QMessageBox.question(self, "初始化环境", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.setup_status.setText("\u23f3 正在初始化环境...")
        self.setup_status.setStyleSheet("color: #FFA726; font-style: normal;")
        self.status_bar.showMessage("正在初始化...")
        self._start_task(_run_setup)
        self._worker.finished.connect(self._on_setup_done)
        self._worker.error.connect(self._on_setup_error)

    def _on_setup_done(self, result):
        self.setup_status.setText("\u2705 环境初始化完成")
        self.setup_status.setStyleSheet("color: #4CAF50; font-style: normal;")
        self.status_bar.showMessage("初始化完成")

    def _on_setup_error(self, message: str):
        self.setup_status.setText("\u274c 初始化失败")
        self.setup_status.setStyleSheet("color: #EF5350; font-style: normal;")
        self.status_bar.showMessage(f"初始化失败: {message[:50]}")

    def _on_test_api(self):
        """测试 API 连接是否可用。"""
        import requests
        from media2md.utils.config import load_env, get_api_config
        
        cfg = load_env()
        api_cfg = get_api_config(cfg)
        key = api_cfg.get("api_key", "")
        url = api_cfg.get("api_url", "")
        
        if not key or key == "your_api_key_here":
            # Try to read from the input field
            key_text = self.api_key_input.text().strip()
            if key_text and key_text != "********":
                config_set("api.key", key_text)
                cfg = load_env()  # reload
                api_cfg = get_api_config(cfg)
                key = api_cfg.get("api_key", "")
        
        if not key or key == "your_api_key_here":
            self.api_test_status.setText("❌ 请先输入 API Key")
            self.api_test_status.setStyleSheet("color: #f44336; padding: 4px 0;")
            return
        
        self.api_test_status.setText("⏳ 测试中...")
        self.api_test_status.setStyleSheet("color: #FFA726; padding: 4px 0;")
        QApplication.processEvents()
        
        try:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": api_cfg.get("model_name", "deepseek-chat"),
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                self.api_test_status.setText("✅ 连接成功")
                self.api_test_status.setStyleSheet("color: #4CAF50; padding: 4px 0;")
            else:
                self.api_test_status.setText(f"❌ 错误 {resp.status_code}: {resp.text[:60]}")
                self.api_test_status.setStyleSheet("color: #f44336; padding: 4px 0;")
        except requests.exceptions.ConnectTimeout:
            self.api_test_status.setText("❌ 连接超时")
            self.api_test_status.setStyleSheet("color: #f44336; padding: 4px 0;")
        except requests.exceptions.ConnectionError:
            self.api_test_status.setText("❌ 无法连接（网络或URL错误）")
            self.api_test_status.setStyleSheet("color: #f44336; padding: 4px 0;")
        except Exception as e:
            self.api_test_status.setText(f"❌ {str(e)[:40]}")
            self.api_test_status.setStyleSheet("color: #f44336; padding: 4px 0;")

    # ---- 播放控制 ----

    def _on_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText("\u25b6")
        else:
            self.player.play()
            self.play_btn.setText("\u23f8")

    def _on_seek(self, position: int):
        self.player.setPosition(position)

    def _on_position_changed(self, position: int = 0):
        if not self.player.duration():
            return
        pos = self.player.position()
        dur = self.player.duration()
        self.position_slider.setValue(pos)
        self.time_label.setText(f"{self._ms_to_str(pos)} / {self._ms_to_str(dur)}")
        self.highlighter.update_position(pos)

    def _on_duration_changed(self, duration: int):
        self.position_slider.setMaximum(max(duration, 1))

    def _on_player_error(self, error, error_string):
        QMessageBox.warning(self, "播放器错误", error_string)

    @staticmethod
    def _ms_to_str(ms: int) -> str:
        s = ms // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("media2md-player")
    window = Media2MDWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
