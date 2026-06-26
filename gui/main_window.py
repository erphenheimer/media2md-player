"""media2md-player GUI 主窗口 — 视频播放器 + 文稿面板。"""

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
    QToolBar,
    QStatusBar,
    QStyle,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QComboBox,
    QGroupBox,
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
from media2md.utils.config import load_env, get_api_config, get_whisper_config


# ========================================================================
# 设置对话框
# ========================================================================

class SettingsDialog(QDialog):
    """Whisper 参数设置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(450, 400)

        from media2md.utils.config import config_list, config_set

        self._config_set = config_set
        layout = QVBoxLayout(self)

        whisper_group = QGroupBox("Whisper 转写设置")
        whisper_form = QFormLayout(whisper_group)

        cfgs = {c["key"]: c for c in config_list()}

        self.model_combo = QComboBox()
        for m in ["tiny", "base", "small", "medium", "large"]:
            self.model_combo.addItem(m)
        self.model_combo.setCurrentText(cfgs.get("whisper.model", {}).get("value", "medium"))
        whisper_form.addRow("模型大小:", self.model_combo)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["cuda", "cpu"])
        self.device_combo.setCurrentText(cfgs.get("whisper.device", {}).get("value", "cuda"))
        whisper_form.addRow("转写设备:", self.device_combo)

        self.compute_combo = QComboBox()
        self.compute_combo.addItems(["float16", "int8", "float32"])
        current = cfgs.get("whisper.compute_type", {}).get("value", "float16")
        self.compute_combo.setCurrentText(current)
        whisper_form.addRow("计算精度:", self.compute_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["zh", "en", "ja", "auto"])
        self.lang_combo.setCurrentText(cfgs.get("whisper.language", {}).get("value", "zh"))
        whisper_form.addRow("语言:", self.lang_combo)

        layout.addWidget(whisper_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        self._config_set("whisper.model", self.model_combo.currentText())
        self._config_set("whisper.device", self.device_combo.currentText())
        self._config_set("whisper.compute_type", self.compute_combo.currentText())
        self._config_set("whisper.language", self.lang_combo.currentText())
        self.accept()


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
    """主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("media2md-player")
        self.resize(1200, 700)

        self.current_file: Path | None = None
        self.transcript: Transcript | None = None
        self.config = load_env()
        self.api_config = get_api_config(self.config)

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)

        # 后台线程管理
        self._worker_thread: QThread | None = None
        self._worker: Worker | None = None

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        self._position_timer = QTimer(self)
        self._position_timer.setInterval(200)
        self._position_timer.timeout.connect(self._on_position_changed)

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
        process_menu = menubar.addMenu("处理(&P)")
        correct_action = QAction("AI 文稿修正(&C)", self)
        correct_action.triggered.connect(self._on_correct)
        process_menu.addAction(correct_action)
        guide_action = QAction("生成导读(&G)", self)
        guide_action.triggered.connect(self._on_generate_guide)
        process_menu.addAction(guide_action)

        # 设置菜单
        settings_menu = menubar.addMenu("设置(&S)")
        setup_action = QAction("初始化环境(&I)...", self)
        setup_action.triggered.connect(self._on_setup)
        settings_menu.addAction(setup_action)
        pref_action = QAction("Whisper 参数(&P)...", self)
        pref_action.triggered.connect(self._on_settings)
        settings_menu.addAction(pref_action)

    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self._on_play_pause)
        toolbar.addWidget(self.play_btn)
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(0)
        self.position_slider.sliderMoved.connect(self._on_seek)
        toolbar.addWidget(self.position_slider)
        self.time_label = QLabel("00:00 / 00:00")
        toolbar.addWidget(self.time_label)

    def _build_central(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：视频播放器
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(400, 300)
        video_layout.addWidget(self.video_widget)
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.errorOccurred.connect(self._on_player_error)
        self.load_btn = QPushButton("打开音视频文件...")
        self.load_btn.clicked.connect(self._on_open_file)
        video_layout.addWidget(self.load_btn)
        splitter.addWidget(video_container)

        # 右侧：文稿面板
        transcript_container = QWidget()
        transcript_layout = QVBoxLayout(transcript_container)
        toolbar_right = QHBoxLayout()
        self.btn_transcribe = QPushButton("转写")
        self.btn_transcribe.clicked.connect(self._on_transcribe)
        self.btn_correct = QPushButton("AI 修正")
        self.btn_correct.clicked.connect(self._on_correct)
        self.btn_guide = QPushButton("导读")
        self.btn_guide.clicked.connect(self._on_generate_guide)
        self.btn_export = QPushButton("导出 Markdown")
        self.btn_export.clicked.connect(self._on_export)
        for btn in [self.btn_transcribe, self.btn_correct, self.btn_guide, self.btn_export]:
            toolbar_right.addWidget(btn)
        transcript_layout.addLayout(toolbar_right)
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setReadOnly(True)
        self.transcript_edit.setFont(QFont("Microsoft YaHei", 10))
        transcript_layout.addWidget(self.transcript_edit)
        splitter.addWidget(transcript_container)
        splitter.setSizes([500, 500])
        self.setCentralWidget(splitter)
        self.highlighter = TranscriptHighlighter(self.transcript_edit)

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

    def _load_transcript(self):
        if not self.current_file:
            return
        self.transcript = extract_transcript(self.current_file)
        if self.transcript.segments:
            self._display_transcript(self.transcript)
        else:
            audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
            is_audio = self.current_file.suffix.lower() in audio_exts
            if is_audio:
                hint = "音频文件无内嵌字幕。\n\n点击「转写」按钮使用 Whisper 语音识别提取文稿。"
            else:
                hint = "未找到字幕。\n\n点击「转写」按钮使用 Whisper 语音识别。"
            self.transcript_edit.setPlainText(hint)

    def _display_transcript(self, transcript: Transcript):
        md = transcript.to_markdown()
        self.transcript_edit.setPlainText(md)
        self.highlighter.set_transcript(transcript)
        self.status_bar.showMessage(
            f"文稿已加载: {len(transcript.segments)} 段落 (来源: {transcript.source_type.value})"
        )

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
        self.transcript = result
        self._display_transcript(self.transcript)


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
        self.transcript = corrected
        self._display_transcript(corrected)
        self.status_bar.showMessage(
            f"修正完成: {len(result.logs)} 处修改, {len(result.review_needed)} 处待审核"
        )


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
        self.transcript_edit.setPlainText(guide_md)
        self.status_bar.showMessage("导读生成完成")


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
        """打开设置对话框。"""
        dlg = SettingsDialog(self)
        dlg.exec()

    def _on_setup(self):
        """初始化环境。"""
        from media2md.pipeline.setup import check_env, run_setup as _run_setup

        env = check_env()
        if env.ready_to_transcribe:
            QMessageBox.information(self, "初始化", "环境已就绪，无需初始化。")
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

        self.status_bar.showMessage("正在初始化...")
        self._start_task(_run_setup)
        self._worker.finished.connect(lambda r: self.status_bar.showMessage("初始化完成"))
        self._worker.error.connect(lambda e: self.status_bar.showMessage(f"初始化失败: {e[:50]}"))

    # ---- 播放控制 ----

    def _on_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

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
