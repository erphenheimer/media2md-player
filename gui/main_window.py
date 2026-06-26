"""media2md-player GUI 主窗口 — 视频播放器 + 文稿面板。"""

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")

from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QAction, QFont, QColor, QTextCursor
from PyQt6.QtMultimedia import QMediaPlayer
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
)

from media2md.models.transcript import Transcript, SourceType
from media2md.pipeline.extractor import extract_transcript
from media2md.pipeline.transcriber import transcribe_file, resolve_whisper
from media2md.pipeline.corrector import correct_transcript, load_api_config
from media2md.pipeline.guide_generator import generate_guide
from media2md.pipeline.exporter import (
    export_transcript,
    export_guide,
    generate_output_paths,
)
from media2md.utils.config import load_env, get_api_config


class TranscriptHighlighter:
    """文稿高亮跟踪器 — 根据播放位置高亮对应段落。"""

    def __init__(self, text_edit: QTextEdit):
        self.text_edit = text_edit
        self.segments: list[dict] = []  # [{start_ms, end_ms, block_start, block_end}]
        self.current_index = -1

    def set_transcript(self, transcript: Transcript):
        """加载文稿并记录段落位置。"""
        self.segments = []
        self.current_index = -1
        doc = self.text_edit.document()
        for seg in transcript.segments:
            # 查找段落文本在文档中的位置
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
        """根据播放位置 ms 更新高亮。"""
        # 找到当前应高亮的段落索引
        new_index = -1
        for i, seg in enumerate(self.segments):
            if seg["start_ms"] <= position_ms <= seg["end_ms"]:
                new_index = i
                break

        if new_index == self.current_index:
            return

        # 清除旧高亮
        if self.current_index >= 0:
            old_seg = self.segments[self.current_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(old_seg["block_start"])
            cursor.setPosition(old_seg["block_end"], QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
            fmt.setBackground(QColor("transparent"))
            cursor.setCharFormat(fmt)

        # 设置新高亮
        if new_index >= 0:
            new_seg = self.segments[new_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(new_seg["block_start"])
            cursor.setPosition(new_seg["block_end"], QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
            fmt.setBackground(QColor("#FFFF00"))  # 黄色高亮
            cursor.setCharFormat(fmt)

            # 滚动到可见区域
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

        self.current_index = new_index


class Media2MDWindow(QMainWindow):
    """主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("media2md-player")
        self.resize(1200, 700)

        # 状态
        self.current_file: Path | None = None
        self.transcript: Transcript | None = None
        self.config = load_env()
        self.api_config = get_api_config(self.config)

        # 构建 UI
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        # 播放器定时器 — 跟踪播放位置
        self._position_timer = QTimer(self)
        self._position_timer.setInterval(200)  # 200ms 更新一次
        self._position_timer.timeout.connect(self._on_position_changed)

    def _build_menu(self):
        """构建菜单栏。"""
        menubar = self.menuBar()

        # 文件菜单
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

        # 处理菜单
        process_menu = menubar.addMenu("处理(&P)")
        correct_action = QAction("AI 文稿修正(&C)", self)
        correct_action.triggered.connect(self._on_correct)
        process_menu.addAction(correct_action)

        guide_action = QAction("生成导读(&G)", self)
        guide_action.triggered.connect(self._on_generate_guide)
        process_menu.addAction(guide_action)

    def _build_toolbar(self):
        """构建工具栏。"""
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        # 从系统图标获取播放控制图标
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self._on_play_pause)
        toolbar.addWidget(self.play_btn)

        # 进度条
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(0)
        self.position_slider.sliderMoved.connect(self._on_seek)
        toolbar.addWidget(self.position_slider)

        # 时间标签
        self.time_label = QLabel("00:00 / 00:00")
        toolbar.addWidget(self.time_label)

    def _build_central(self):
        """构建中央区域（视频播放器 + 文稿面板）。"""
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：视频播放器
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(400, 300)
        video_layout.addWidget(self.video_widget)

        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        # 加载按钮（当无视频时显示）
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
        """构建状态栏。"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    # ========== 事件处理 ==========

    def _on_open_file(self):
        """打开音视频或字幕文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "媒体文件 (*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.m4a *.srt *.vtt *.ass);;所有文件 (*.*)",
        )
        if not path:
            return

        self.current_file = Path(path)
        self.setWindowTitle(f"media2md-player - {self.current_file.name}")
        self.status_bar.showMessage(f"已打开: {self.current_file.name}")

        # 加载文稿
        self._load_transcript()

        # 如果是视频/音频，加载到播放器
        if self.current_file.suffix.lower() in (
            ".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".wmv", ".m4v",
            ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
        ):
            self.player.setSource(QUrl.fromLocalFile(str(self.current_file)))
            self.load_btn.hide()
            self.play_btn.setEnabled(True)
            self._position_timer.start()

    def _load_transcript(self):
        """从当前文件加载文稿。"""
        if not self.current_file:
            return

        self.transcript = extract_transcript(self.current_file)
        if self.transcript.segments:
            self._display_transcript(self.transcript)
        else:
            # 判断文件类型显示不同提示
            audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
            is_audio = self.current_file.suffix.lower() in audio_exts
            if is_audio:
                hint = "音频文件无内嵌字幕。\n\n点击「转写」按钮使用 Whisper 语音识别提取文稿。"
            else:
                hint = "未找到字幕。\n\n点击「转写」按钮使用 Whisper 语音识别。"
            self.transcript_edit.setPlainText(hint)

    def _display_transcript(self, transcript: Transcript):
        """在面板中显示文稿。"""
        md = transcript.to_markdown()
        self.transcript_edit.setPlainText(md)
        self.highlighter.set_transcript(transcript)
        self.status_bar.showMessage(
            f"文稿已加载: {len(transcript.segments)} 段落 (来源: {transcript.source_type.value})"
        )

    def _on_transcribe(self):
        """Whisper 转写。"""
        if not self.current_file:
            QMessageBox.warning(self, "提示", "请先打开文件。")
            return

        self.status_bar.showMessage("正在转写...")
        QApplication.processEvents()

        try:
            self.transcript = transcribe_file(
                self.current_file,
                process_dir=self.current_file.parent / ".process",
            )
            self._display_transcript(self.transcript)
        except RuntimeError as e:
            QMessageBox.critical(self, "转写失败", str(e))
            self.status_bar.showMessage("转写失败")

    def _on_correct(self):
        """AI 修正文稿。"""
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

        self.status_bar.showMessage("正在 AI 修正...")
        QApplication.processEvents()

        result = correct_transcript(self.transcript, api_config=self.api_config)
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

    def _on_generate_guide(self):
        """生成导读。"""
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

        self.status_bar.showMessage("正在生成导读...")
        QApplication.processEvents()

        guide = generate_guide(
            full_text,
            title=self.current_file.stem if self.current_file else "",
            api_config=self.api_config,
        )
        guide_md = guide.to_markdown()
        self.transcript_edit.setPlainText(guide_md)
        self.status_bar.showMessage("导读生成完成")

    def _on_export(self):
        """导出 Markdown。"""
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

    def _on_play_pause(self):
        """播放/暂停切换。"""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def _on_seek(self, position: int):
        """进度条拖拽跳转。"""
        self.player.setPosition(position)

    def _on_position_changed(self, position: int = 0):
        """播放位置更新。"""
        if not self.player.duration():
            return

        pos = self.player.position()
        dur = self.player.duration()
        self.position_slider.setValue(pos)
        self.time_label.setText(
            f"{self._ms_to_str(pos)} / {self._ms_to_str(dur)}"
        )

        # 更新文稿高亮
        self.highlighter.update_position(pos)

    def _on_duration_changed(self, duration: int):
        """时长变化时更新进度条范围。"""
        self.position_slider.setMaximum(max(duration, 1))

    def _on_player_error(self, error, error_string):
        """播放器错误处理。"""
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
