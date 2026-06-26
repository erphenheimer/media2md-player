"""Markdown 导出器 — 将文稿和导读导出为 Markdown 文件。"""

from __future__ import annotations

from pathlib import Path

from media2md.models.transcript import Transcript
from media2md.models.guide import ReadingGuide


def export_transcript(
    transcript: Transcript,
    output_path: str | Path,
    with_timestamps: bool = True,
) -> Path:
    """将文稿导出为 Markdown 文件。

    Args:
        transcript: 文稿对象
        output_path: 输出路径
        with_timestamps: 是否包含时间戳

    Returns:
        Path: 输出文件路径
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if with_timestamps:
        content = transcript.to_markdown()
    else:
        # 纯文本模式（不含时间戳）
        lines = [f"# {transcript.title or '文稿'}", ""]
        lines.append(f"- 来源: {transcript.source_type.value}")
        lines.append(f"- 源文件: {transcript.source_path}")
        lines.append("")
        lines.append(transcript.full_text)
        content = "\n".join(lines)

    path.write_text(content, encoding="utf-8")
    return path


def export_guide(
    guide: ReadingGuide,
    output_path: str | Path,
) -> Path:
    """将导读导出为 Markdown 文件。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(guide.to_markdown(), encoding="utf-8")
    return path


def export_correction_log(
    original_transcript: Transcript,
    corrected_transcript: Transcript,
    output_path: str | Path,
) -> Path:
    """导出修正前后对照 Markdown。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# 文稿修正对照", ""]
    lines.append("| 时间 | 原文 | 修正后 |")
    lines.append("| --- | --- | --- |")

    # 建立修正映射
    corrected_map = {}
    for seg in corrected_transcript.segments:
        corrected_map[seg.start_ms] = seg.text

    for seg in original_transcript.segments:
        original = seg.text
        corrected = corrected_map.get(seg.start_ms, original)
        ts = seg.format_timestamp(seg.start_ms)
        if original != corrected:
            lines.append(f"| {ts} | ~~{original}~~ | **{corrected}** |")
        else:
            lines.append(f"| {ts} | {original} | {corrected} |")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def generate_output_paths(
    stem: str,
    output_dir: str | Path,
) -> dict:
    """生成标准输出文件路径。

    Returns:
        dict: {"transcript": ..., "guide": ..., "corrected": ..., "correction_log": ...}
    """
    out = Path(output_dir) / stem
    return {
        "transcript": out / "transcript.md",
        "guide": out / "guide.md",
        "corrected": out / "corrected.md",
        "correction_log": out / "correction_log.md",
    }
