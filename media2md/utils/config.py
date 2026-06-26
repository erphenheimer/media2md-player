"""配置加载工具。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def find_project_root() -> Path:
    """从当前目录向上查找项目根（包含 pyproject.toml）。"""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return cwd


def load_env(env_path: Optional[str | Path] = None) -> dict:
    """加载 .env 文件中的配置。

    不依赖 python-dotenv，内置简单解析器。
    优先级：已设置的环境变量 > .env 文件 > 默认值
    """
    config = {}

    # 确定 .env 路径
    if env_path is None:
        env_path = find_project_root() / ".env"
    env_file = Path(env_path)

    # 从 .env 文件读取
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            # 仅当环境变量未设置时使用 .env 值
            if key not in os.environ:
                config[key] = value

    # 环境变量覆盖
    for key in [
        "API_KEY", "API_URL", "MODEL_NAME", "API_PROVIDER",
        "WHISPER_CTRANSLATE2_EXE", "WHISPER_MODEL_DIR",
        "WHISPER_MODEL_CACHE_DIR", "WHISPER_LOCAL_FILES_ONLY",
        "FFMPEG_PATH",
        "PROCESS_DIR", "OUTPUT_DIR",
    ]:
        val = os.environ.get(key, config.get(key, ""))
        if val:
            config[key] = val

    return config


def get_api_config(config: Optional[dict] = None) -> dict:
    """获取 API 配置子集。"""
    cfg = config or load_env()
    return {
        "api_key": cfg.get("API_KEY", ""),
        "api_url": cfg.get("API_URL", "https://api.deepseek.com/v1/chat/completions"),
        "model_name": cfg.get("MODEL_NAME", "deepseek-chat"),
        "api_provider": cfg.get("API_PROVIDER", "deepseek"),
    }
