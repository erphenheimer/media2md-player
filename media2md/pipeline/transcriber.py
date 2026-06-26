"""Whisper 语音转写器 — 封装 whisper-ctranslate2 CLI。"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from media2md.models.transcript import Transcript, TranscriptSegment, SourceType
from media2md.utils.timestamp import parse_srt_timestamp


def get_whisper_config(env_path: Optional[str] = None) -> dict:
    """从 .env 或已知本地配置获取 Whisper 路径配置。"""
    config = {
        "exe": None,
        "model_dir": None,
        "model_cache_dir": None,
        "local_files_only": False,
    }

    # 尝试从环境变量读取
    for key, cfg_key in [
        ("WHISPER_CTRANSLATE2_EXE", "exe"),
        ("WHISPER_MODEL_DIR", "model_dir"),
        ("WHISPER_MODEL_CACHE_DIR", "model_cache_dir"),
    ]:
        val = os.environ.get(key, "").strip()
        if val:
            config[cfg_key] = val

    if os.environ.get("WHISPER_LOCAL_FILES_ONLY", "").strip().lower() == "true":
        config["local_files_only"] = True

    return config


def probe_known_local_profile() -> dict | None:
    """探测已知的本机 ACER Whisper 配置。

    在 ACER 机器上验证过以下路径:
    D:/AI_Video_Knowledge_Base/.venv/Scripts/whisper-ctranslate2.exe
    D:/AI_Video_Knowledge_Base/models/models--Systran--faster-whisper-medium/snapshots/08e178d48790749d25932bbc082711ddcfdfbc4f/model.bin
    """
    candidates = {
        "exe": "D:/AI_Video_Knowledge_Base/.venv/Scripts/whisper-ctranslate2.exe",
        "model_dir": "D:/AI_Video_Knowledge_Base/models/models--Systran--faster-whisper-medium/snapshots/08e178d48790749d25932bbc082711ddcfdfbc4f",
        "model_cache_dir": "D:/AI_Video_Knowledge_Base/models",
    }

    exe_path = Path(candidates["exe"])
    model_bin = Path(candidates["model_dir"]) / "model.bin"

    if exe_path.exists() and model_bin.exists():
        return {
            "exe": str(exe_path),
            "model_dir": str(candidates["model_dir"]),
            "model_cache_dir": str(candidates["model_cache_dir"]),
            "local_files_only": True,
        }
    return None


def resolve_whisper() -> dict:
    """解析 Whisper 可执行文件路径和模型路径。

    优先级:
    1. .env 配置的 WHISPER_CTRANSLATE2_EXE
    2. 已知本地 ACER 配置
    3. PATH 中的 whisper-ctranslate2
    """
    config = get_whisper_config()

    # 如果 .env 已配置且路径存在，直接使用
    if config["exe"] and Path(config["exe"]).exists():
        return config

    # 探测已知本地配置
    local = probe_known_local_profile()
    if local:
        return local

    # 回退到 PATH
    exe = _find_in_path("whisper-ctranslate2")
    if exe:
        return {"exe": exe, "model_dir": None, "model_cache_dir": None, "local_files_only": False}

    return config  # 返回空配置，调用方处理


def _find_in_path(name: str) -> str | None:
    """在 PATH 中查找可执行文件。"""
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_dir) / f"{name}.exe"
        if candidate.exists():
            return str(candidate)
        candidate = Path(path_dir) / name
        if candidate.exists():
            return str(candidate)
    return None


def extract_audio_from_video(
    video_path: str | Path,
    output_path: str | Path,
    ffmpeg_path: str = "ffmpeg",
) -> bool:
    """从视频文件中提取音频为 16kHz mono WAV。"""
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
        return Path(output_path).exists()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def parse_whisper_output(output_dir: str | Path, stem: str) -> Transcript | None:
    """解析 Whisper 的输出文件为 Transcript。

    支持格式优先级: .json > .srt > .txt
    """
    out_dir = Path(output_dir)

    # 优先解析 JSON (whisper-ctranslate2 输出)
    json_path = out_dir / f"{stem}.json"
    if json_path.exists():
        return _parse_whisper_json(json_path)

    # 其次 SRT
    srt_path = out_dir / f"{stem}.srt"
    if srt_path.exists():
        return _parse_whisper_srt(srt_path)

    # 最后纯文本
    txt_path = out_dir / f"{stem}.txt"
    if txt_path.exists():
        text = txt_path.read_text(encoding="utf-8-sig").strip()
        if text:
            return Transcript(
                segments=[TranscriptSegment(start_ms=0, end_ms=0, text=text)],
                source_type=SourceType.WHISPER,
                source_path=str(txt_path),
            )
    return None


def _parse_whisper_json(json_path: str | Path) -> Transcript:
    """解析 whisper-ctranslate2 的 JSON 输出。"""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    segments = []
    for seg in data.get("segments", []):
        segments.append(
            TranscriptSegment(
                start_ms=int(seg.get("start", 0) * 1000),
                end_ms=int(seg.get("end", 0) * 1000),
                text=seg.get("text", "").strip(),
                confidence=seg.get("confidence", 1.0),
            )
        )
    return Transcript(
        segments=segments,
        source_type=SourceType.WHISPER,
        source_path=str(json_path),
    )


def _parse_whisper_srt(srt_path: str | Path) -> Transcript:
    """解析 Whisper 输出的 SRT 文件。"""
    from media2md.utils.subtitle_parser import parse_srt
    transcript = parse_srt(Path(srt_path).read_text(encoding="utf-8-sig"))
    transcript.source_type = SourceType.WHISPER
    transcript.source_path = str(srt_path)
    return transcript


def transcribe(
    audio_path: str | Path,
    output_dir: str | Path,
    model: str = "medium",
    language: str = "zh",
    device: str = "cuda",
    compute_type: str = "float16",
    whisper_config: Optional[dict] = None,
) -> Transcript:
    """使用 whisper-ctranslate2 转写音频文件。

    Args:
        audio_path: 音频文件路径
        output_dir: Whisper 输出目录
        model: 模型大小 (tiny/base/small/medium/large)
        language: 语言代码
        device: cuda 或 cpu
        compute_type: float16/int8/float32
        whisper_config: Whisper 配置 (来自 resolve_whisper())

    Returns:
        Transcript: 带时间戳的文稿

    Raises:
        RuntimeError: 如果转写失败或找不到 Whisper
    """
    audio = Path(audio_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = audio.stem

    config = whisper_config or resolve_whisper()
    exe = config.get("exe")
    if not exe:
        raise RuntimeError(
            "找不到 whisper-ctranslate2。请配置 .env 中的 WHISPER_CTRANSLATE2_EXE，"
            "或将其加入 PATH。"
        )

    # 构建命令行
    cmd = [
        exe,
        str(audio),
        "--model", model,
        "--language", language,
        "--output_format", "json",
        "--output_dir", str(out_dir),
        "--device", device,
        "--compute_type", compute_type,
        "--verbose", "False",
    ]

    # 添加模型路径参数
    if config.get("model_dir"):
        cmd.extend(["--model_directory", config["model_dir"]])
    elif config.get("model_cache_dir"):
        cmd.extend(["--model_dir", config["model_cache_dir"]])

    if config.get("local_files_only"):
        cmd.append("--local_files_only")
        cmd.append("True")

    # 环境变量（CUDA DLL 处理）
    env = os.environ.copy()
    if device == "cuda" and config.get("exe"):
        exe_path = Path(config["exe"])
        venv_base = exe_path.parent.parent
        nvidia_dirs = [
            venv_base / "Lib/site-packages/nvidia/cublas/bin",
            venv_base / "Lib/site-packages/nvidia/cuda_nvrtc/bin",
            venv_base / "Lib/site-packages/nvidia/cuda_runtime/bin",
            venv_base / "Lib/site-packages/nvidia/cudnn/bin",
        ]
        extra_paths = [str(d) for d in nvidia_dirs if d.exists()]
        if extra_paths:
            env["PATH"] = os.pathsep.join(extra_paths + [env.get("PATH", "")])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600, env=env
        )
        if result.returncode != 0:
            # CUDA 失败时自动回退 CPU
            if device == "cuda" and "cublas" in (result.stderr or "").lower():
                return transcribe(
                    audio_path, output_dir, model, language,
                    device="cpu", compute_type="int8", whisper_config=config
                )
            raise RuntimeError(
                f"Whisper 转写失败 (exit={result.returncode}): {result.stderr}"
            )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Whisper 转写超时（>1小时）")

    # 解析输出
    transcript = parse_whisper_output(out_dir, stem)
    if transcript is None:
        raise RuntimeError(f"Whisper 执行成功但未找到输出文件: {out_dir}/{stem}.*")

    return transcript


def transcribe_file(
    source_path: str | Path,
    process_dir: str | Path,
    ffmpeg_path: str = "ffmpeg",
    model: str = "medium",
    language: str = "zh",
    device: str = "cuda",
    compute_type: str = "float16",
) -> Transcript:
    """处理单个文件：如果是视频先提取音频，再转写。

    Args:
        source_path: 源文件路径（音频或视频）
        process_dir: 工作目录（存放中间文件）
        ffmpeg_path: ffmpeg 路径
        model/language/device/compute_type: Whisper 参数

    Returns:
        Transcript
    """
    src = Path(source_path)
    proc = Path(process_dir)
    proc.mkdir(parents=True, exist_ok=True)

    # 检查是否已有缓存
    cache_file = proc / "transcripts" / f"{src.stem}.json"
    if cache_file.exists():
        return _parse_whisper_json(cache_file)

    # 判断输入类型
    video_exts = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".wmv", ".m4v"}
    audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}

    audio_dir = proc / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir = proc / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() in video_exts:
        # 视频：提取音频
        wav_path = audio_dir / f"{src.stem}.wav"
        if not wav_path.exists():
            print(f"[transcribe] 提取音频: {src.name} -> {wav_path.name}")
            ok = extract_audio_from_video(src, wav_path, ffmpeg_path=ffmpeg_path)
            if not ok:
                raise RuntimeError(f"音频提取失败: {src}")
        audio_input = wav_path
    elif src.suffix.lower() in audio_exts:
        # 音频：直接转写
        audio_input = src
    else:
        raise ValueError(f"不支持的文件类型: {src.suffix}")

    print(f"[transcribe] 转写: {audio_input.name}")
    transcript = transcribe(
        audio_input,
        output_dir=transcript_dir,
        model=model,
        language=language,
        device=device,
        compute_type=compute_type,
    )
    return transcript
