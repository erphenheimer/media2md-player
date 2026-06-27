"""GUI 批量处理标签页 — 文件列表 / 并行数调节 / 逐文件进度。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QAbstractItemView,
    QFrame,
)

from media2md.pipeline.batcher import BatchManager, TaskStatus


class BatchTab(QWidget):
    """批量处理标签页。"""

    def __init__(self, batch_manager: BatchManager, parent=None):
        super().__init__(parent)
        self.batch = batch_manager
        self._build_ui()

        # 连接信号
        self.batch.task_started.connect(self._on_task_started)
        self.batch.task_completed.connect(self._on_task_completed)
        self.batch.task_failed.connect(self._on_task_failed)
        self.batch.progress_updated.connect(self._on_progress_updated)
        self.batch.all_completed.connect(self._on_all_completed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ---- 顶部工具栏 ----
        toolbar = QHBoxLayout()

        self.add_btn = QPushButton("＋ 添加文件")
        self.add_btn.setObjectName("primary_btn")
        self.add_btn.clicked.connect(self._on_add_files)
        toolbar.addWidget(self.add_btn)

        self.remove_btn = QPushButton("移除选中")
        self.remove_btn.clicked.connect(self._on_remove_selected)
        toolbar.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("清除已完成")
        self.clear_btn.clicked.connect(self._on_clear_completed)
        toolbar.addWidget(self.clear_btn)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("并行数:"))
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setMinimum(1)
        self.parallel_spin.setMaximum(16)
        self.parallel_spin.setValue(1)
        self.parallel_spin.setFixedWidth(60)
        self.parallel_spin.valueChanged.connect(self._on_parallel_changed)
        toolbar.addWidget(self.parallel_spin)

        layout.addLayout(toolbar)

        # ---- 分隔线 ----
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444444;")
        layout.addWidget(sep)

        # ---- 任务列表 ----
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "文件名", "状态", "用时"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)

        # 拖拽排序
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDragDropOverwriteMode(False)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table.model().rowsMoved.connect(self._on_rows_moved)

        layout.addWidget(self.table)

        # ---- 底部进度 ----
        bottom = QHBoxLayout()

        self.start_btn = QPushButton("▶ 开始处理")
        self.start_btn.setObjectName("primary_btn")
        self.start_btn.clicked.connect(self._on_start)
        bottom.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        bottom.addWidget(self.stop_btn)

        bottom.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0 / 0")
        bottom.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        bottom.addWidget(self.status_label)

        layout.addLayout(bottom)

    # ---- 槽函数 ----

    def _on_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择要处理的文件", "",
            "媒体文件 (*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.m4a *.srt *.vtt *.ass);;所有文件 (*.*)"
        )
        if not paths:
            return

        indices = self.batch.add_files(paths)
        for idx in indices:
            task = self.batch.tasks[idx]
            self._add_table_row(idx, task)

        self.update()

    def _add_table_row(self, index: int, task):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(task.order + 1)))
        self.table.setItem(row, 1, QTableWidgetItem(task.file_path.name))
        status_item = QTableWidgetItem(task.status.value)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, status_item)
        self.table.setItem(row, 3, QTableWidgetItem("--"))
        self.table.item(row, 0).setFlags(self.table.item(row, 0).flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.item(row, 1).setFlags(self.table.item(row, 1).flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.item(row, 2).setFlags(self.table.item(row, 2).flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.item(row, 3).setFlags(self.table.item(row, 3).flags() & ~Qt.ItemFlag.ItemIsEditable)
        # 保存 task index 到 row 的 user data
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, index)

    def _on_remove_selected(self):
        rows = sorted(set(r.row() for r in self.table.selectedItems()), reverse=True)
        for row in rows:
            index = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if index is not None:
                if not self.batch.remove_task(index):
                    continue
            self.table.removeRow(row)
        # 刷新序号
        self._refresh_numbers()

    def _on_clear_completed(self):
        self.batch.clear_completed()
        self.table.setRowCount(0)
        for i, task in enumerate(self.batch.tasks):
            self._add_table_row(i, task)

    def _on_parallel_changed(self, value: int):
        self.batch.max_workers = value

    def _on_rows_moved(self):
        """拖拽后重建顺序。"""
        indices = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) is not None:
                indices.append(item.data(Qt.ItemDataRole.UserRole))
        # 重建 batch.tasks 顺序
        self.batch.tasks = [self.batch.tasks[i] for i in indices]
        for i, t in enumerate(self.batch.tasks):
            t.order = i
        self._refresh_numbers()

    def _refresh_numbers(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                idx = item.data(Qt.ItemDataRole.UserRole)
                if idx is not None and idx < len(self.batch.tasks):
                    item.setText(str(self.batch.tasks[idx].order + 1))

    def _on_start(self):
        if self.batch.is_running:
            return
        if not self.batch.tasks:
            QMessageBox.warning(self, "提示", "请先添加文件。")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.parallel_spin.setEnabled(False)

        # 重置已完成的任务
        self.batch.reset()
        self._refresh_statuses()

        self.batch.set_pipeline_fn(self._get_pipeline_fn())
        self.batch.max_workers = self.parallel_spin.value()
        self.batch.start()

    def _get_pipeline_fn(self):
        """返回可以被 batcher 调用的管线函数。"""
        from media2md.pipeline.orchestrator import run_full_pipeline
        return run_full_pipeline

    def _on_stop(self):
        self.batch.stop()
        self._reset_controls()
        self.status_label.setText("已停止")

    def _on_task_started(self, index: int, file_name: str):
        self._update_status(index, TaskStatus.RUNNING.value)
        self.status_label.setText(f"处理中: {file_name}")

    def _on_task_completed(self, index: int, file_name: str):
        self._update_status(index, TaskStatus.COMPLETED.value)
        # 更新用时
        if index < len(self.batch.tasks):
            sec = self.batch.tasks[index].duration_sec
            self._update_time(index, sec)

    def _on_task_failed(self, index: int, file_name: str, error: str):
        self._update_status(index, TaskStatus.FAILED.value)

    def _on_progress_updated(self, completed: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(completed)
        self.progress_bar.setFormat(f"{completed} / {total}")

    def _on_all_completed(self):
        self._reset_controls()
        done = sum(1 for t in self.batch.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.batch.tasks if t.status == TaskStatus.FAILED)
        total = len(self.batch.tasks)
        if failed > 0:
            self.status_label.setText(f"完成: {done}/{total} ({failed} 个失败)")
            QMessageBox.warning(self, "批量处理完成", f"{done} 个完成, {failed} 个失败")
        else:
            self.status_label.setText(f"全部完成: {done}/{total}")
            QMessageBox.information(self, "批量处理完成", f"全部 {done} 个文件处理完成")

    # ---- 辅助 ----

    def _update_status(self, index: int, status_text: str):
        """更新表格中指定任务的状态列。"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == index:
                self.table.item(row, 2).setText(status_text)
                # 失败标红
                if status_text == TaskStatus.FAILED.value:
                    self.table.item(row, 2).setForeground(
                        self.palette().color(self.palette().ColorRole.BrightText)
                        if hasattr(self, "palette") else None
                    )
                break

    def _update_time(self, index: int, seconds: float):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == index:
                if seconds < 60:
                    self.table.item(row, 3).setText(f"{seconds:.0f}s")
                else:
                    self.table.item(row, 3).setText(f"{seconds/60:.1f}min")
                break

    def _refresh_statuses(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 2)
            if item:
                item.setText(TaskStatus.PENDING.value)

    def _reset_controls(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.parallel_spin.setEnabled(True)
