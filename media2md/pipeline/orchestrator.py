"""全流程编排器 (占位，后续 Phase 实现)。"""

import os


def run_full_pipeline(
    input_path: str,
    output_dir: str = "output",
    force: bool = False,
    skip_correct: bool = False,
    skip_guide: bool = False,
):
    """
    全流程：提取字幕/Whisper → AI 修正 → 导读生成 → Markdown 导出。
    """
    print(f"=== media2md 全流程处理 ===")
    print(f"输入: {input_path}")
    print(f"输出: {output_dir}")
    print(f"跳过修正: {skip_correct}")
    print(f"跳过导读: {skip_guide}")

    os.makedirs(output_dir, exist_ok=True)
    print("[待实现] 此管线将在后续 Phase 中逐步构建。")
