"""字幕文件解析器 — 支持 SRT、VTT、ASS 格式。"""

from __future__ import annotations

import re
from pathlib import Path

from media2md.models.transcript import Transcript, TranscriptSegment, SourceType
from media2md.utils.timestamp import parse_srt_timestamp


def parse_srt(content: str, source_path: str = "") -> Transcript:
    """解析 SRT 格式字幕为 Transcript。"""
    segments = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        # 跳过序号行（纯数字）
        if not re.match(r"^\d+$", lines[0].strip()):
            continue
        # 时间戳行: HH:MM:SS,mmm --> HH:MM:SS,mmm
        ts_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})",
            lines[1],
        )
        if not ts_match:
            continue
        start_ms = parse_srt_timestamp(ts_match.group(1))
        end_ms = parse_srt_timestamp(ts_match.group(2))
        text = "\n".join(lines[2:]).strip()
        # 去除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)
        if text:
            segments.append(
                TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text)
            )

    return Transcript(
        segments=segments,
        source_type=SourceType.EXTERNAL_SUBTITLE,
        source_path=source_path,
    )


def parse_vtt(content: str, source_path: str = "") -> Transcript:
    """解析 WebVTT 格式字幕为 Transcript。"""
    segments = []
    # 移除 VTT 头部
    if content.startswith("WEBVTT"):
        content = re.sub(r"^WEBVTT.*?\n\n", "", content, count=1, flags=re.DOTALL)

    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
        # 跳过注释和样式块
        if lines[0].startswith("NOTE") or lines[0].startswith("STYLE"):
            continue
        # 时间戳行: HH:MM:SS.mmm --> HH:MM:SS.mmm
        ts_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})",
            lines[0],
        )
        if not ts_match:
            continue
        start_ms = parse_srt_timestamp(ts_match.group(1))
        end_ms = parse_srt_timestamp(ts_match.group(2))
        text = "\n".join(lines[1:]).strip()
        # 去除 cue 设置 (align:start position:...)
        text = re.sub(r"^.*?:\S+\s*", "", text).strip()
        text = re.sub(r"<[^>]+>", "", text)
        if text:
            segments.append(
                TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text)
            )

    return Transcript(
        segments=segments,
        source_type=SourceType.EXTERNAL_SUBTITLE,
        source_path=source_path,
    )


def parse_ass(content: str, source_path: str = "") -> Transcript:
    """解析 ASS/SSA 格式字幕为 Transcript（提取 Dialogue 行）。"""
    segments = []
    # 找到 [Events] 之后的 Format 行确定列顺序
    format_match = re.search(
        r"\[Events\].*?Format:\s*(.*?)[\r\n]", content, re.DOTALL | re.IGNORECASE
    )
    if not format_match:
        return Transcript(segments=[], source_type=SourceType.EXTERNAL_SUBTITLE, source_path=source_path)

    columns = [c.strip().lower() for c in format_match.group(1).split(",")]
    try:
        start_idx = columns.index("start")
        end_idx = columns.index("end")
        text_idx = columns.index("text")
    except ValueError:
        return Transcript(segments=[], source_type=SourceType.EXTERNAL_SUBTITLE, source_path=source_path)

    for match in re.finditer(
        r"^Dialogue:\s*(.*?)$", content, re.MULTILINE
    ):
        parts = match.group(1).split(",", maxsplit=max(start_idx, end_idx, text_idx))
        if len(parts) <= max(start_idx, end_idx, text_idx):
            continue
        # 解析 ASS 时间格式: H:MM:SS.cc (百分之一秒)
        start_str = parts[start_idx].strip()
        end_str = parts[end_idx].strip()
        text = ",".join(parts[text_idx:]).strip()
        # 去除 ASS 样式覆盖码
        text = re.sub(r"\{[^}]*\}", "", text).strip()
        text = text.replace("\\N", "\n").replace("\\n", "\n")
        if not text:
            continue
        try:
            start_ms = _parse_ass_timestamp(start_str)
            end_ms = _parse_ass_timestamp(end_str)
        except ValueError:
            continue
        segments.append(
            TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text)
        )

    return Transcript(
        segments=segments,
        source_type=SourceType.EXTERNAL_SUBTITLE,
        source_path=source_path,
    )


def _parse_ass_timestamp(ts: str) -> int:
    """解析 ASS 时间戳: H:MM:SS.cc (百分之一秒)"""
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s_cc = parts
        s, cc = s_cc.split(".")
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(cc) * 10
    return 0


def parse_subtitle(file_path: str | Path) -> Transcript:
    """根据扩展名自动选择解析器。"""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8-sig")

    if path.suffix.lower() == ".srt":
        return parse_srt(content, source_path=str(path))
    elif path.suffix.lower() == ".vtt":
        return parse_vtt(content, source_path=str(path))
    elif path.suffix.lower() in (".ass", ".ssa"):
        return parse_ass(content, source_path=str(path))
    else:
        raise ValueError(f"不支持的字幕格式: {path.suffix}")
