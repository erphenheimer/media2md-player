"""AI 文稿修正器 — 调用外部 API（DeepSeek/Kimi）修正 Whisper 转写错误。"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

from media2md.models.transcript import Transcript, TranscriptSegment


@dataclass
class CorrectionLog:
    """单条修正记录。"""
    original_text: str
    corrected_text: str
    start_ms: int
    end_ms: int
    changes: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class CorrectionResult:
    """修正结果。"""
    corrected_segments: list[TranscriptSegment] = field(default_factory=list)
    logs: list[CorrectionLog] = field(default_factory=list)
    review_needed: list[CorrectionLog] = field(default_factory=list)


def load_api_config(env_path: Optional[str] = None) -> dict:
    """加载 API 配置。"""
    config = {
        "api_key": os.environ.get("API_KEY", ""),
        "api_url": os.environ.get(
            "API_URL", "https://api.deepseek.com/v1/chat/completions"
        ),
        "model_name": os.environ.get("MODEL_NAME", "deepseek-chat"),
        "api_provider": os.environ.get("API_PROVIDER", "deepseek"),
    }
    return config


def build_correction_prompt(source_text: str, context: Optional[str] = None) -> str:
    """构建修正提示词。"""
    system_prompt = """你是一个专业的视频文稿校对专家。你的任务是对语音识别（ASR）输出的文稿进行修正。

修正原则：
1. 只修正 ASR 识别错误（同音字、专有名词、数字错误），不改变原意和表达方式
2. 不要添加原文没有的内容
3. 保持原文的风格和语气
4. 对于不确定的内容，用 [??] 标记并保持原文
5. 只输出修正后的文本，不要添加任何解释

常见错误类型：
- 同音字错误：如"你好"被识别为"你号"
- 专有名词错误：如人名、地名、产品名识别错误
- 数字错误：如"2023年"被识别为"两零二三年"
- 断句错误：如一句话被错误分成两段"""

    user_prompt = f"请修正以下语音识别文稿中的错误：\n\n{source_text}"

    if context:
        user_prompt = (
            f"以下是视频文稿的上下文信息：\n{context}\n\n"
            f"请修正以下语音识别文稿中的错误：\n\n{source_text}"
        )

    return system_prompt, user_prompt


def build_batch_correction_prompt(segments: list[dict]) -> str:
    """批量修正：将多个段落一起发送给 API。"""
    system_prompt = """你是一个专业的视频文稿校对专家。请逐段修正以下语音识别文稿。

每一段格式为：
[开始时间-->结束时间] 文本

修正原则：
1. 只修正 ASR 识别错误，不改变原意
2. 保持时间戳不变，只修改文本内容
3. 不确定的内容用 [??] 标记
4. 按同样的格式输出修正后的每一段
5. 不要添加任何解释"""

    lines = []
    for seg in segments:
        start = _ms_to_time_str(seg["start_ms"])
        end = _ms_to_time_str(seg["end_ms"])
        lines.append(f"[{start}-->{end}] {seg['text']}")

    user_prompt = "请逐段修正以下文稿：\n\n" + "\n".join(lines)
    return system_prompt, user_prompt


def _ms_to_time_str(ms: int) -> str:
    h, r = divmod(ms, 3600000)
    m, s = divmod(r // 1000, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def call_api(
    system_prompt: str,
    user_prompt: str,
    api_config: dict,
    max_retries: int = 3,
) -> str | None:
    """调用兼容 OpenAI 的 chat-completions API。"""
    api_key = api_config.get("api_key", "")
    if not api_key or api_key == "your_api_key_here":
        print("[corrector] WARN: API_KEY 未配置，跳过 API 调用")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": api_config.get("model_name", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    url = api_config.get("api_url", "")
    if not url:
        print("[corrector] WARN: API_URL 未配置")
        return None

    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except requests.exceptions.Timeout:
            print(f"[corrector] TIME_OUT 超时 (尝试 {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            print(f"[corrector] ERROR: API 请求失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
    return None


def parse_corrected_output(
    output_text: str, original_segments: list[TranscriptSegment]
) -> CorrectionResult:
    """解析 API 返回的修正结果。"""
    result = CorrectionResult()
    lines = output_text.strip().split("\n")
    corrected_map = {}

    import re as _re
    for line in lines:
        m = _re.match(r"\[(\d{2}:\d{2}:\d{2})-->\s*(\d{2}:\d{2}:\d{2})\]\s*(.+)", line)
        if m:
            start_str = m.group(1)
            text = m.group(3).strip()
            h1, m1, s1 = start_str.split(":")
            start_ms = int(h1) * 3600000 + int(m1) * 60000 + int(s1) * 1000
            corrected_map[start_ms] = text

    for seg in original_segments:
        if seg.start_ms in corrected_map:
            new_text = corrected_map[seg.start_ms]
            has_uncertainty = "[??]" in new_text
            log = CorrectionLog(
                original_text=seg.text,
                corrected_text=new_text,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                changes=[] if new_text == seg.text else ["AI 修正"],
            )
            if has_uncertainty:
                result.review_needed.append(log)
            else:
                result.logs.append(log)
            result.corrected_segments.append(
                TranscriptSegment(
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    text=new_text,
                    confidence=seg.confidence,
                )
            )
        else:
            # 未修正的段落保持原样
            result.corrected_segments.append(seg)

    return result


def correct_transcript(
    transcript: Transcript,
    api_config: Optional[dict] = None,
    output_dir: Optional[str | Path] = None,
) -> CorrectionResult:
    """修正 Transcript 中的文稿内容。

    Args:
        transcript: 原始文稿
        api_config: API 配置（从 load_api_config() 获取）
        output_dir: 可选的输出目录（保存修正日志）

    Returns:
        CorrectionResult: 包含修正后的段落和修正日志
    """
    config = api_config or load_api_config()

    # 构建批量修正请求
    segments_data = [
        {"start_ms": seg.start_ms, "end_ms": seg.end_ms, "text": seg.text}
        for seg in transcript.segments
    ]

    if not segments_data:
        return CorrectionResult(corrected_segments=list(transcript.segments))

    system_prompt, user_prompt = build_batch_correction_prompt(segments_data)
    output_text = call_api(system_prompt, user_prompt, config)

    if output_text is None:
        # API 调用失败或未配置，返回原始文稿
        return CorrectionResult(corrected_segments=list(transcript.segments))

    result = parse_corrected_output(output_text, transcript.segments)

    # 保存修正日志
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        log_path = out / "asr_corrections.tsv"
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(["start_ms", "end_ms", "original", "corrected", "changes"])
            for log in result.logs:
                writer.writerow(
                    [log.start_ms, log.end_ms, log.original_text, log.corrected_text, "; ".join(log.changes)]
                )
        review_path = out / "review_needed.md"
        if result.review_needed:
            with open(review_path, "w", encoding="utf-8") as f:
                f.write("# Review Needed\n\n")
                f.write("以下段落包含不确定的修正，需要人工审核：\n\n")
                for log in result.review_needed:
                    f.write(f"- [{log.start_ms}ms] {log.original_text}\n")
                    f.write(f"  -> {log.corrected_text}\n\n")

    return result
