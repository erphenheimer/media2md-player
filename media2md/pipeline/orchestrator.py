"""全流程编排器 — 整合提取→修正→导读→导出。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Windows GBK 控制台兼容
os.environ.setdefault("PYTHONUTF8", "1")

from media2md.models.transcript import Transcript, SourceType
from media2md.pipeline.extractor import extract_transcript
from media2md.pipeline.transcriber import transcribe_file, resolve_whisper
from media2md.pipeline.corrector import correct_transcript
from media2md.pipeline.guide_generator import generate_guide
from media2md.pipeline.exporter import (
    export_transcript,
    export_guide,
    export_correction_log,
    generate_output_paths,
)
from media2md.utils.config import load_env, get_api_config


def run_full_pipeline(
    input_path: str,
    output_dir: str = "output",
    force: bool = False,
    skip_correct: bool = False,
    skip_guide: bool = False,
    include_timestamps: bool = True,
    process_dir: Optional[str] = None,
):
    """全流程：提取字幕/Whisper -> AI 修正 -> 导读生成 -> Markdown 导出。"""
    src = Path(input_path)
    if not src.exists():
        print(f"[ERROR] 文件不存在: {input_path}")
        return

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config = load_env()
    api_config = get_api_config(config)
    ffmpeg_path = config.get("FFMPEG_PATH", "ffmpeg")
    proc_dir = Path(process_dir) if process_dir else (out_dir / ".process")

    stem = src.stem
    outputs = generate_output_paths(stem, out_dir)

    print(f"\n{'='*50}")
    print(f"[PROC] 处理: {src.name}")
    print(f"[OUT]  输出: {out_dir}")
    print(f"{'='*50}\n")

    # ========== Step 1: 提取文稿 ==========
    print("[1/3] 提取文稿")

    if not force and outputs["transcript"].exists() and outputs["transcript"].stat().st_size > 0:
        print(f"  [SKIP] 已存在: {outputs['transcript'].name}")
        transcript = None
    else:
        transcript = extract_transcript(src, ffmpeg_path=ffmpeg_path)

        if not transcript.segments and transcript.source_type == SourceType.WHISPER:
            print("  [INFO] 未找到字幕，启动 Whisper 转写...")
            try:
                transcript = transcribe_file(
                    src,
                    process_dir=proc_dir,
                    ffmpeg_path=ffmpeg_path,
                )
            except RuntimeError as e:
                print(f"  [ERROR] Whisper 转写失败: {e}")
                return
        elif not transcript.segments:
            print("  [WARN] 未能提取到文稿内容")
            return
        else:
            print(f"  [OK] 提取到 {len(transcript.segments)} 个段落 (来源: {transcript.source_type.value})")

        export_transcript(transcript, outputs["transcript"], with_timestamps=include_timestamps)
        print(f"  [SAVE] 原始文稿 -> {outputs['transcript'].name}")

    # ========== Step 2: AI 修正 ==========
    if not skip_correct:
        print("\n[2/3] AI 文稿修正")

        if not force and outputs["corrected"].exists() and outputs["corrected"].stat().st_size > 0:
            print(f"  [SKIP] 已存在: {outputs['corrected'].name}")
        else:
            if transcript is None:
                print("  [WARN] 需要重新处理以获取文稿数据")
                return

            if transcript.source_type in (SourceType.EXTERNAL_SUBTITLE, SourceType.EMBEDDED_SUBTITLE):
                print("  [INFO] 字幕来源，无需修正")
            else:
                result = correct_transcript(transcript, api_config=api_config, output_dir=proc_dir / "logs")
                corrected_transcript = Transcript(
                    segments=result.corrected_segments,
                    source_type=transcript.source_type,
                    source_path=transcript.source_path,
                    title=transcript.title,
                )
                export_transcript(corrected_transcript, outputs["corrected"], with_timestamps=include_timestamps)
                export_correction_log(transcript, corrected_transcript, outputs["correction_log"])
                print(f"  [OK] 修正完成: {len(result.logs)} 处修改, {len(result.review_needed)} 处待审核")
                print(f"  [SAVE] 修正文稿 -> {outputs['corrected'].name}")
                print(f"  [SAVE] 修正对照 -> {outputs['correction_log'].name}")
                transcript = corrected_transcript

    # ========== Step 3: 生成导读 ==========
    if not skip_guide:
        print("\n[3/3] 生成导读")

        if not force and outputs["guide"].exists() and outputs["guide"].stat().st_size > 0:
            print(f"  [SKIP] 已存在: {outputs['guide'].name}")
        else:
            if transcript is None:
                print("  [WARN] 需要重新处理以获取文稿数据")
                return

            full_text = transcript.full_text
            if not full_text:
                print("  [WARN] 文稿为空，跳过导读")
            else:
                guide = generate_guide(full_text, title=stem, api_config=api_config)
                export_guide(guide, outputs["guide"])
                print(f"  [SAVE] 导读 -> {outputs['guide'].name}")

    print(f"\n{'='*50}")
    print(f"[DONE] 处理完成: {stem}")
    print(f"{'='*50}")
    print(f"\n输出文件:")
    for key, path in outputs.items():
        if path.exists():
            print(f"  [FILE] {path.relative_to(out_dir)}")
    print()
