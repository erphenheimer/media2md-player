"""导读数据模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict


@dataclass
class ReadingGuide:
    """结构化导读内容。"""

    title: str = ""
    one_line_conclusion: str = ""
    core_pain_points: list[str] = field(default_factory=list)
    core_ideas: list[str] = field(default_factory=list)
    scenario_actions: list[str] = field(default_factory=list)
    action_steps: list[str] = field(default_factory=list)
    limits_and_caveats: list[str] = field(default_factory=list)
    retrieval_keywords: list[str] = field(default_factory=list)
    source_path: str = ""

    def to_markdown(self) -> str:
        """导出为结构化 Markdown。"""
        lines = [f"# {self.title or '导读'}", ""]

        sections = [
            ("## 一句话结论", self.one_line_conclusion, False),
            ("## 核心痛点", self.core_pain_points, True),
            ("## 核心观点", self.core_ideas, True),
            ("## 场景化建议", self.scenario_actions, True),
            ("## 行动步骤", self.action_steps, True),
            ("## 局限与注意事项", self.limits_and_caveats, True),
            ("## 检索关键词", self.retrieval_keywords, True),
        ]

        for heading, content, is_list in sections:
            lines.append(heading)
            lines.append("")
            if isinstance(content, str) and content:
                lines.append(content)
            elif isinstance(content, list) and content:
                for item in content:
                    lines.append(f"- {item}")
            else:
                lines.append("（待补充）")
            lines.append("")

        if self.source_path:
            lines.append(f"## 来源")
            lines.append("")
            lines.append(f"- {self.source_path}")
            lines.append("")

        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent)
