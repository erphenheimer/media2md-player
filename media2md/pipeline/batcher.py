"""批量任务队列 — 带并行 Worker Pool 的任务管理器。"""

from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal


class TaskStatus(str, Enum):
    PENDING = "等待"
    RUNNING = "处理中"
    COMPLETED = "完成"
    FAILED = "失败"
    SKIPPED = "跳过"


@dataclass
class BatchTask:
    """单个批量任务。"""

    file_path: Path
    status: TaskStatus = TaskStatus.PENDING
    error: Optional[str] = None
    output_dir: Optional[Path] = None
    duration_sec: float = 0.0
    order: int = 0  # 处理顺序（用于排序）


class BatchManager(QObject):
    """批量任务管理器 — 队列控制 + 并行执行。"""

    # === 信号 ===
    task_started = pyqtSignal(int, str)           # (index, file_name)
    task_progress = pyqtSignal(int, str, float)    # (index, file_name, progress_0_1)
    task_completed = pyqtSignal(int, str)          # (index, file_name)
    task_failed = pyqtSignal(int, str, str)        # (index, file_name, error)
    all_completed = pyqtSignal()
    progress_updated = pyqtSignal(int, int)        # (completed_count, total_count)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: list[BatchTask] = []
        self._max_workers: int = 1
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: dict = {}
        self._running = False
        self._pipeline_fn: Optional[Callable] = None

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @max_workers.setter
    def max_workers(self, value: int):
        self._max_workers = max(1, value)

    @property
    def is_running(self) -> bool:
        return self._running

    def set_pipeline_fn(self, fn: Callable):
        """设置处理函数。签名为 fn(file_path: Path, output_dir: Path) -> None"""
        self._pipeline_fn = fn

    # ---- 队列操作 ----

    def add_files(self, file_paths: list[Path | str]) -> list[int]:
        """添加文件到任务列表末尾。返回新添加的任务索引列表。"""
        indices = []
        for fp in file_paths:
            p = Path(fp)
            idx = len(self.tasks)
            self.tasks.append(BatchTask(file_path=p, order=idx))
            indices.append(idx)
        return indices

    def remove_task(self, index: int) -> bool:
        """删除一个任务。如果任务正在运行则无法删除。"""
        if 0 <= index < len(self.tasks):
            if self.tasks[index].status == TaskStatus.RUNNING:
                return False
            self.tasks.pop(index)
            # 重建 order
            for i, t in enumerate(self.tasks):
                t.order = i
            return True
        return False

    def move_task(self, from_index: int, to_index: int) -> bool:
        """拖拽移动任务顺序。"""
        if 0 <= from_index < len(self.tasks) and 0 <= to_index < len(self.tasks):
            task = self.tasks.pop(from_index)
            self.tasks.insert(to_index, task)
            for i, t in enumerate(self.tasks):
                t.order = i
            return True
        return False

    def clear_completed(self):
        """清除已完成/失败/跳过的任务。"""
        self.tasks = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        for i, t in enumerate(self.tasks):
            t.order = i

    def reset(self):
        """重置所有任务为等待状态。"""
        for t in self.tasks:
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED):
                t.status = TaskStatus.PENDING
                t.error = None

    # ---- 执行控制 ----

    def start(self, output_base: str | Path = "output"):
        """启动批量处理。"""
        if self._running:
            return
        if not self._pipeline_fn:
            return
        if not self.tasks:
            return

        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._futures = {}
        output_base = Path(output_base)
        output_base.mkdir(parents=True, exist_ok=True)

        # 只处理 PENDING 的任务
        for i, task in enumerate(self.tasks):
            if task.status != TaskStatus.PENDING:
                continue

            task.output_dir = output_base / task.file_path.stem
            task.status = TaskStatus.RUNNING

            future = self._executor.submit(
                self._run_single_task, i, task
            )
            self._futures[future] = i

        # 在后台线程里等待所有任务完成
        from PyQt6.QtCore import QThread
        self._monitor_thread = QThread(self)
        self._monitor = _CompletionMonitor(self._futures)
        self._monitor.moveToThread(self._monitor_thread)
        self._monitor_thread.started.connect(self._monitor.run)
        self._monitor.finished.connect(self._on_all_completed)
        self._monitor.finished.connect(self._monitor_thread.quit)
        self._monitor_thread.start()

    def _run_single_task(self, index: int, task: BatchTask):
        """在 Worker 线程中执行单个任务。"""
        try:
            self.task_started.emit(index, task.file_path.name)

            t0 = time.time()
            self._pipeline_fn(
                input_path=str(task.file_path),
                output_dir=str(task.output_dir),
            )
            task.duration_sec = time.time() - t0

            task.status = TaskStatus.COMPLETED
            self.task_completed.emit(index, task.file_path.name)
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = f"{e}\n{traceback.format_exc()}"
            self.task_failed.emit(index, task.file_path.name, str(e))
        finally:
            completed = sum(1 for t in self.tasks if t.status in (
                TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED
            ))
            total = len(self.tasks)
            self.progress_updated.emit(completed, total)

    def stop(self):
        """停止所有任务（取消尚未启动的任务）。"""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        # 将 RUNNING → PENDING（实际可能还在跑，但标记为可重试）
        for t in self.tasks:
            if t.status == TaskStatus.RUNNING:
                t.status = TaskStatus.PENDING

    def _on_all_completed(self):
        self._running = False
        self.all_completed.emit()


class _CompletionMonitor(QObject):
    """在后台线程中等待所有 Future 完成。"""
    finished = pyqtSignal()

    def __init__(self, futures: dict):
        super().__init__()
        self._futures = futures

    def run(self):
        for future in as_completed(self._futures):
            pass  # 结果已经在 _run_single_task 里处理了
        self.finished.emit()
