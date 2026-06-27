"""media2md CLI 入口。"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="media2md",
        description="音视频 → 文稿 → AI 修正 → 导读 → Markdown 导出",
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # media2md process
    p_process = sub.add_parser("process", help="全流程处理：提取→修正→导读→导出")
    p_process.add_argument("input", help="输入文件路径（音视频/字幕）")
    p_process.add_argument("--output", "-o", default="output", help="输出目录 (默认: output)")
    p_process.add_argument("--force", action="store_true", help="强制重新处理已存在的文件")
    p_process.add_argument("--skip-correct", action="store_true", help="跳过 AI 修正步骤")
    p_process.add_argument("--skip-guide", action="store_true", help="跳过导读生成步骤")
    p_process.add_argument("--no-timestamp", action="store_true", help="导出文稿不含时间戳")

    # media2md transcribe
    p_trans = sub.add_parser("transcribe", help="仅转写：字幕提取或 Whisper 转写")
    p_trans.add_argument("input", help="输入文件路径")
    p_trans.add_argument("--output", "-o", default="output", help="输出目录")

    # media2md correct
    p_corr = sub.add_parser("correct", help="仅 AI 修正文稿")
    p_corr.add_argument("input", help="文稿文件路径 (.txt 或 .json)")
    p_corr.add_argument("--output", "-o", default="output", help="输出目录")

    # media2md guide
    p_guide = sub.add_parser("guide", help="仅生成导读")
    p_guide.add_argument("input", help="文稿文件路径")
    p_guide.add_argument("--output", "-o", default="output", help="输出目录")

    # media2md export
    p_export = sub.add_parser("export", help="仅导出 Markdown")
    p_export.add_argument("input", help="文稿数据路径")
    p_export.add_argument("--output", "-o", default="output", help="输出目录")
    p_export.add_argument("--no-timestamp", action="store_true", help="导出文稿不含时间戳")

    # media2md setup
    p_setup = sub.add_parser("setup", help="初始化环境（安装 Whisper + 下载模型）")
    p_setup.add_argument("--model", default="medium", help="模型大小: tiny/base/small/medium/large (默认: medium)")
    p_setup.add_argument("--check", action="store_true", help="仅检测环境，不安装")
    p_setup.add_argument("--auto", action="store_true", help="自动模式，不询问")

    # media2md config
    p_config = sub.add_parser("config", help="配置管理")
    p_config.add_argument("key", nargs="?", default=None, help="配置项键名, 如 whisper.device")
    p_config.add_argument("value", nargs="?", default=None, help="配置项值")
    p_config.add_argument("--list", action="store_true", dest="list_all", help="列出所有配置")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # 路由到对应处理器
    if args.command == "process":
        run_process(args)
    elif args.command == "transcribe":
        run_transcribe(args)
    elif args.command == "correct":
        run_correct(args)
    elif args.command == "guide":
        run_guide(args)
    elif args.command == "export":
        run_export(args)
    elif args.command == "setup":
        run_setup(args)
    elif args.command == "config":
        run_config(args)


def run_process(args):
    """全流程处理。"""
    from media2md.pipeline.orchestrator import run_full_pipeline

    run_full_pipeline(
        input_path=args.input,
        output_dir=args.output,
        force=args.force,
        skip_correct=args.skip_correct,
        skip_guide=args.skip_guide,
        include_timestamps=not args.no_timestamp,
    )


def run_transcribe(args):
    """仅转写。"""
    from pathlib import Path
    from media2md.pipeline.extractor import extract_transcript
    from media2md.pipeline.transcriber import transcribe_file
    from media2md.models.transcript import SourceType
    from media2md.pipeline.exporter import export_transcript

    src = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    transcript = extract_transcript(src)
    if not transcript.segments and transcript.source_type == SourceType.WHISPER:
        print("未找到字幕，启动 Whisper 转写...")
        transcript = transcribe_file(src, process_dir=out_dir / ".process")

    output_path = out_dir / f"{src.stem}_transcript.md"
    export_transcript(transcript, output_path)
    print(f"[DONE] 转写完成: {output_path}")


def run_correct(args):
    """仅修正。"""
    from pathlib import Path
    from media2md.models.transcript import Transcript
    from media2md.pipeline.corrector import correct_transcript
    from media2md.utils.config import get_api_config

    src = Path(args.input)
    if src.suffix == ".json":
        transcript = Transcript.from_json(src.read_text(encoding="utf-8"))
    else:
        # 纯文本文件，构造单段 Transcript
        text = src.read_text(encoding="utf-8")
        from media2md.models.transcript import TranscriptSegment
        transcript = Transcript(
            segments=[TranscriptSegment(start_ms=0, end_ms=0, text=text)],
        )

    api_config = get_api_config()
    result = correct_transcript(transcript, api_config=api_config)

    out_path = Path(args.output) / f"{src.stem}_corrected.md"
    from media2md.models.transcript import Transcript as T
    corrected = T(
        segments=result.corrected_segments,
        source_type=transcript.source_type,
    )
    from media2md.pipeline.exporter import export_transcript
    export_transcript(corrected, out_path)
    print(f"[DONE] 修正完成: {out_path}")


def run_guide(args):
    """仅导读。"""
    from pathlib import Path
    from media2md.pipeline.guide_generator import generate_guide
    from media2md.utils.config import get_api_config

    text = Path(args.input).read_text(encoding="utf-8")
    api_config = get_api_config()
    guide = generate_guide(text, api_config=api_config)

    out_path = Path(args.output) / f"{Path(args.input).stem}_guide.md"
    from media2md.pipeline.exporter import export_guide
    export_guide(guide, out_path)
    print(f"[DONE] 导读生成: {out_path}")


def run_export(args):
    """仅导出（将现有文稿/导读重新导出为 Markdown）。"""
    from pathlib import Path
    from media2md.models.transcript import Transcript
    from media2md.pipeline.exporter import export_transcript, export_guide

    src = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if src.suffix == ".json":
        transcript = Transcript.from_json(src.read_text(encoding="utf-8"))
        out_path = out_dir / f"{src.stem}_transcript.md"
        export_transcript(transcript, out_path, with_timestamps=not args.no_timestamp)
        print(f"[DONE] 导出完成: {out_path}")
    else:
        print(f"跳过: {src.name}（目前仅支持 .json 格式导出）")


def run_setup(args):
    """初始化环境。"""
    from media2md.pipeline.setup import check_env, run_setup as _run_setup

    if args.check:
        env = check_env()
        print("=== 环境检测 ===")
        for k, v in env.to_dict().items():
            icon = "OK" if k.endswith("_ok") and v else "MISSING" if k.endswith("_ok") else ""
            if k.endswith("_ok"):
                print(f"  {k}: {icon}")
            elif k == "python":
                print(f"  Python: {v.split()[0]}")
            elif k == "ffmpeg":
                print(f"  FFmpeg: {v or 'NOT FOUND'}")
            elif k == "whisper":
                print(f"  Whisper: {v or 'NOT INSTALLED'}")
            elif k == "cuda":
                print(f"  CUDA: {'AVAILABLE' if v else 'NOT DETECTED'}")
        print(f"\n  转写就绪: {'YES' if env.ready_to_transcribe else 'NO'}")
        return

    success = _run_setup(model=args.model, auto=args.auto)
    sys.exit(0 if success else 1)


def run_config(args):
    """配置管理。"""
    from media2md.utils.config import config_list, config_get, config_set, ALL_SETTINGS

    if args.list_all or (not args.key and not args.value):
        print("=== 当前配置 ===")
        for item in config_list():
            mark = "*" if item["is_set"] else " "
            print(f"  [{mark}] {item['key']} = {item['value']}")
            print(f"        {item['description']}")
        print(f"\n  [*] = 已自定义  [ ] = 使用默认值")
        print(f"  使用 media2md config <key> <value> 修改配置")
        print(f"  例如: media2md config whisper.device cpu")
        return

    if args.key and args.value:
        env_key = config_set(args.key, args.value)
        print(f"已设置: {env_key}={config_get(args.key)}")
        return

    if args.key:
        val = config_get(args.key)
        if args.key in ALL_SETTINGS:
            desc = ALL_SETTINGS[args.key][1]
            default = ALL_SETTINGS[args.key][0]
            print(f"{args.key} = {val}  (默认: {default}, {desc})")
        else:
            print(f"{args.key} = {val or '(未设置)'}")
        return


if __name__ == "__main__":
    main()
