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
    p_process.add_argument("input", help="输入文件路径")
    p_process.add_argument("--output", "-o", default="output", help="输出目录 (默认: output)")
    p_process.add_argument("--force", action="store_true", help="强制重新处理已存在的文件")
    p_process.add_argument("--skip-correct", action="store_true", help="跳过 AI 修正步骤")
    p_process.add_argument("--skip-guide", action="store_true", help="跳过导读生成步骤")

    # media2md transcribe
    p_trans = sub.add_parser("transcribe", help="仅转写：字幕提取或 Whisper 转写")
    p_trans.add_argument("input", help="输入文件路径")
    p_trans.add_argument("--output", "-o", default="output", help="输出目录")

    # media2md correct
    p_corr = sub.add_parser("correct", help="仅 AI 修正文稿")
    p_corr.add_argument("input", help="文稿文件路径 (txt 或 json)")
    p_corr.add_argument("--output", "-o", default="output", help="输出目录")

    # media2md guide
    p_guide = sub.add_parser("guide", help="仅生成导读")
    p_guide.add_argument("input", help="文稿文件路径")
    p_guide.add_argument("--output", "-o", default="output", help="输出目录")

    # media2md export
    p_export = sub.add_parser("export", help="仅导出 Markdown")
    p_export.add_argument("input", help="文稿或导读数据路径")
    p_export.add_argument("--output", "-o", default="output", help="输出目录")

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


def run_process(args):
    """全流程处理（占位）。"""
    from media2md.pipeline.orchestrator import run_full_pipeline
    run_full_pipeline(
        input_path=args.input,
        output_dir=args.output,
        force=args.force,
        skip_correct=args.skip_correct,
        skip_guide=args.skip_guide,
    )


def run_transcribe(args):
    """仅转写（占位）。"""
    print(f"[占位] 转写: {args.input} -> {args.output}")
    print("此功能将在后续 Phase 中实现。")


def run_correct(args):
    """仅修正（占位）。"""
    print(f"[占位] 修正: {args.input} -> {args.output}")
    print("此功能将在后续 Phase 中实现。")


def run_guide(args):
    """仅导读（占位）。"""
    print(f"[占位] 生成导读: {args.input} -> {args.output}")
    print("此功能将在后续 Phase 中实现。")


def run_export(args):
    """仅导出（占位）。"""
    print(f"[占位] 导出 Markdown: {args.input} -> {args.output}")
    print("此功能将在后续 Phase 中实现。")


if __name__ == "__main__":
    main()
