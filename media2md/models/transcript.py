"""音视频文稿数据模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    """文稿来源类型。"""
    EMBEDDED_SUBTITLE = "embedded_subtitle"   # 视频内嵌字幕
    EXTERNAL_SUBTITLE = "external_subtitle"   # 外部字幕文件 (.srt/.vtt/.ass)
    WHISPER = "whisper"                        # Whisper 语音转写
    MANUAL = "manual"                          # 手动输入


@dataclass
class TranscriptSegment:
    """文稿中的一个段落（带时间戳）。"""

    start_ms: int          # 开始时间（毫秒）
    end_ms: int            # 结束时间（毫秒）
    text: str              # 文本内容
    confidence: float = 1.0  # 置信度 (0~1)，Whisper 转写时使用
    speaker: Optional[str] = None  # 说话人（可选，未来支持说话人分离）

    def format_timestamp(self, ms: Optional[int] = None) -> str:
        """将毫秒格式化为 SRT 风格时间戳: HH:MM:SS.mmm"""
        t = ms if ms is not None else self.start_ms
        h, remainder = divmod(t, 3600000)
        m, remainder = divmod(remainder, 60000)
        s, ms_part = divmod(remainder, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms_part:03d}"

    def to_markdown_line(self, include_timestamps: bool = True) -> str:
        """导出为 Markdown 格式。"""
        speaker_tag = f"**{self.speaker}:** " if self.speaker else ""
        if include_timestamps:
            start_ts = self.format_timestamp(self.start_ms)
            end_ts = self.format_timestamp(self.end_ms)
            return f"[{start_ts} --> {end_ts}] {speaker_tag}{self.text}"
        else:
            return f"{speaker_tag}{self.text}"

    def to_srt_block(self, index: int) -> str:
        """导出为 SRT 格式。"""
        start_srt = self.format_timestamp(self.start_ms).replace(".", ",")
        end_srt = self.format_timestamp(self.end_ms).replace(".", ",")
        return f"{index}\n{start_srt} --> {end_srt}\n{self.text}\n"


@dataclass
class Transcript:
    """完整的文稿数据。"""

    segments: list[TranscriptSegment] = field(default_factory=list)
    source_type: SourceType = SourceType.MANUAL
    source_path: str = ""
    title: str = ""
    language: str = ""
    duration_ms: int = 0

    @property
    def full_text(self) -> str:
        """拼接所有段落的纯文本。"""
        return " ".join(seg.text for seg in self.segments)

    def to_markdown(self, include_timestamps: bool = True) -> str:
        """导出为 Markdown 文稿。

        Args:
            include_timestamps: 是否保留时间戳（默认为 True）。
        """
        lines = [f"# {self.title or '文稿'}", ""]
        lines.append(f"- 来源: {self.source_type.value}")
        lines.append(f"- 源文件: {self.source_path}")
        if self.language:
            lines.append(f"- 语言: {self.language}")
        if self.duration_ms:
            lines.append(f"- 时长: {self._format_duration(self.duration_ms)}")
        lines.append("")

        for seg in self.segments:
            lines.append(seg.to_markdown_line(include_timestamps=include_timestamps))

        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        """导出为 JSON。"""
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent)

    @staticmethod
    def _format_duration(ms: int) -> str:
        h, remainder = divmod(ms, 3600000)
        m, s = divmod(remainder // 1000, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        return f"{m}m {s}s"

    @classmethod
    def from_json(cls, data: str | dict) -> "Transcript":
        """从 JSON 恢复 Transcript。"""
        if isinstance(data, str):
            data = json.loads(data)
        segments = [TranscriptSegment(**seg) for seg in data.get("segments", [])]
        data["segments"] = segments
        if "source_type" in data and isinstance(data["source_type"], str):
            data["source_type"] = SourceType(data["source_type"])
        return cls(**data)
