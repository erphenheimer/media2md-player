"""导读生成器 — 基于文稿内容调用 LLM 生成结构化导读。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import requests

from media2md.models.guide import ReadingGuide
from media2md.pipeline.corrector import load_api_config


GUIDE_SYSTEM_PROMPT = """你是一个专业的视频内容分析专家。请根据提供的文稿，生成结构化的导读内容。

请严格按以下 JSON 格式输出，不要添加任何额外内容：

```json
{
  "one_line_conclusion": "一句话总结核心结论",
  "core_pain_points": ["痛点1", "痛点2"],
  "core_ideas": ["核心观点1", "核心观点2", "核心观点3"],
  "scenario_actions": ["场景化建议1", "场景化建议2"],
  "action_steps": ["行动步骤1", "行动步骤2", "行动步骤3"],
  "limits_and_caveats": ["局限1", "注意事项1"],
  "retrieval_keywords": ["关键词1", "关键词2"]
}
```

要求：
1. 每个字段都要有内容，不要留空
2. 核心观点不超过 5 条，每条一句话
3. 检索关键词不超过 10 个，用中文
4. 如果文稿是语音识别结果，在"局限与注意事项"中注明可能存在 ASR 误差
5. 只基于文稿内容，不要添加原文没有的信息
6. 使用与原文相同的语言输出"""


def build_guide_prompt(full_text: str, title: str = "") -> tuple[str, str]:
    """构建导读生成的提示词。"""
    title_str = f"标题：《{title}》\n\n" if title else ""
    user_prompt = (
        f"请根据以下视频文稿生成导读内容：\n\n"
        f"{title_str}"
        f"文稿内容：\n{full_text}"
    )
    return GUIDE_SYSTEM_PROMPT, user_prompt


def parse_guide_response(response_text: str) -> dict | None:
    """从 API 响应中解析 JSON 内容。"""
    text = response_text.strip()

    # 尝试直接解析 JSON
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 尝试从代码块中提取 JSON
    import re
    m = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return None


def generate_guide(
    transcript_text: str,
    title: str = "",
    api_config: Optional[dict] = None,
    language: Optional[str] = None,
) -> ReadingGuide:
    """基于文稿内容生成导读。

    Args:
        transcript_text: 文稿全文
        title: 可选的标题
        api_config: API 配置
        language: 输出语言（None 表示与原文一致）

    Returns:
        ReadingGuide: 结构化导读
    """
    config = api_config or load_api_config()

    # 如果未配置 API，返回空的导读占位
    api_key = config.get("api_key", "")
    if not api_key or api_key == "your_api_key_here":
        print("[guide] WARN: API_KEY 未配置，返回空导读占位")
        return ReadingGuide(title=title, source_path="")

    system_prompt, user_prompt = build_guide_prompt(transcript_text, title)
    if language:
        system_prompt += f"\n\n请用{language}输出。"

    # 调用 API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.get("model_name", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    url = config.get("api_url", "")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = parse_guide_response(content)
            if parsed:
                return ReadingGuide(
                    title=title,
                    one_line_conclusion=parsed.get("one_line_conclusion", ""),
                    core_pain_points=parsed.get("core_pain_points", []),
                    core_ideas=parsed.get("core_ideas", []),
                    scenario_actions=parsed.get("scenario_actions", []),
                    action_steps=parsed.get("action_steps", []),
                    limits_and_caveats=parsed.get("limits_and_caveats", []),
                    retrieval_keywords=parsed.get("retrieval_keywords", []),
                    source_path="",
                )
            else:
                print(f"[guide] WARN: 无法解析 API 响应 (尝试 {attempt+1}/{max_retries})")
        except requests.exceptions.Timeout:
            print(f"[guide] TIME_OUT 超时 (尝试 {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"[guide] ERROR: 错误: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return ReadingGuide(title=title, source_path="")

    return ReadingGuide(title=title, source_path="")
