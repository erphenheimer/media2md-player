"""文稿提取器：优先内嵌字幕 → 外部字幕文件 → 回退到 Whisper。"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from media2md.models.transcript import Transcript, SourceType
from media2md.utils.subtitle_parser import parse_subtitle


def find_external_subtitle(video_path: str | Path) -> Path | None:
    """在视频同级目录查找 .srt/.vtt/.ass 文件。"""
    video = Path(video_path)
    stem = video.stem
    parent = video.parent
    for ext in [".srt", ".vtt", ".ass", ".ssa"]:
        candidate = parent / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def extract_embedded_subtitles(
    video_path: str | Path,
    ffmpeg_path: str = "ffmpeg",
    output_dir: str | None = None,
) -> list[dict]:
    """使用 ffmpeg 提取视频内嵌字幕流。

    返回可用的字幕流信息列表:
    [
        {"index": 0, "language": "eng", "title": "English", "codec": "subrip"},
        ...
    ]
    """
    video = Path(video_path)
    # 探测字幕流
    cmd = [
        ffmpeg_path,
        "-i", str(video),
        "-hide_banner",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, errors='replace', timeout=30
        )
        stderr = result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return []

    # 解析字幕流信息
    streams = []
    for match in re.finditer(
        r"Stream\s+#(\d+:\d+).*?:\s+Subtitle:\s+(\S+)", stderr
    ):
        stream_id = match.group(1)
        codec = match.group(2)
        # 提取语言和标题
        lang_match = re.search(r"\((\w+)\)", match.group(0))
        title_match = re.search(r"title\s*:\s*([^)]+)", match.group(0))
        streams.append({
            "index": stream_id,
            "language": lang_match.group(1) if lang_match else "",
            "title": title_match.group(1).strip() if title_match else "",
            "codec": codec,
        })
    return streams


def extract_embedded_subtitle_to_file(
    video_path: str | Path,
    stream_index: str = "0:0",
    ffmpeg_path: str = "ffmpeg",
    output_path: str | None = None,
) -> Path | None:
    """将指定的内嵌字幕流提取为 .srt 文件。"""
    video = Path(video_path)
    if output_path is None:
        output_path = str(video.with_suffix(".srt"))

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(video),
        "-map", f"0:{stream_index.split(':')[1]}",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=120, check=True)
        return Path(output_path)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return None


def extract_transcript(
    source_path: str | Path,
    ffmpeg_path: str = "ffmpeg",
) -> Transcript:
    """从源文件提取文稿。

    优先级:
    1. 如果是字幕文件 (.srt/.vtt/.ass)，直接解析
    2. 如果是视频/音频文件，先查找同级外部字幕
    3. 如果是视频文件，尝试提取内嵌字幕
    4. 如果均失败，返回空 Transcript（供 Whisper 回退）
    """
    path = Path(source_path)

    # 所有支持的媒体文件后缀
    video_exts = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".wmv", ".m4v"}
    audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
    subtitle_exts = {".srt", ".vtt", ".ass", ".ssa"}

    # 情况 1: 直接是字幕文件
    if path.suffix.lower() in subtitle_exts:
        transcript = parse_subtitle(path)
        transcript.source_type = SourceType.EXTERNAL_SUBTITLE
        return transcript

    # 情况 2: 视频/音频文件 — 先找同级外部字幕
    if path.suffix.lower() in video_exts | audio_exts:
        # 先找外部字幕
        ext_sub = find_external_subtitle(path)
        if ext_sub:
            transcript = parse_subtitle(ext_sub)
            transcript.source_type = SourceType.EXTERNAL_SUBTITLE
            transcript.source_path = str(path)
            return transcript

        # 尝试提取内嵌字幕
        streams = extract_embedded_subtitles(path, ffmpeg_path=ffmpeg_path)
        if streams:
            # 提取第一个字幕流
            srt_path = extract_embedded_subtitle_to_file(
                path, stream_index=streams[0]["index"], ffmpeg_path=ffmpeg_path
            )
            if srt_path and srt_path.exists():
                transcript = parse_subtitle(srt_path)
                transcript.source_type = SourceType.EMBEDDED_SUBTITLE
                transcript.source_path = str(path)
                return transcript

    # 情况 3: 不支持/无字幕 — 返回空 Transcript 供 Whisper 处理
    return Transcript(
        segments=[],
        source_type=SourceType.WHISPER,
        source_path=str(path),
    )


