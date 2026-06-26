"""配置加载与管理 — 读写 .env 文件。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


# ========================================================================
# 路径解析
# ========================================================================

def find_project_root() -> Path:
    """从当前目录向上查找项目根（包含 pyproject.toml）。"""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return cwd


# ========================================================================
# .env 文件读写
# ========================================================================

def _get_env_path() -> Path:
    """获取 .env 文件路径。"""
    return find_project_root() / ".env"


def load_env(env_path: Optional[str | Path] = None) -> dict:
    """加载 .env 文件中的配置。

    内置简单解析器，不依赖 python-dotenv。
    优先级：已设置的环境变量 > .env 文件 > 默认值
    """
    config = {}

    if env_path is None:
        env_path = _get_env_path()
    env_file = Path(env_path)

    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key not in os.environ:
                config[key] = value

    # 环境变量覆盖
    for key in [
        "API_KEY", "API_URL", "MODEL_NAME", "API_PROVIDER",
        "WHISPER_CTRANSLATE2_EXE", "WHISPER_MODEL_DIR",
        "WHISPER_MODEL_CACHE_DIR", "WHISPER_LOCAL_FILES_ONLY",
        "WHISPER_MODEL", "WHISPER_LANGUAGE", "WHISPER_DEVICE",
        "WHISPER_COMPUTE_TYPE",
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


def get_whisper_config(config: Optional[dict] = None) -> dict:
    """获取 Whisper 配置子集。"""
    cfg = config or load_env()
    return {
        "model": cfg.get("WHISPER_MODEL", "medium"),
        "language": cfg.get("WHISPER_LANGUAGE", "zh"),
        "device": cfg.get("WHISPER_DEVICE", "cuda"),
        "compute_type": cfg.get("WHISPER_COMPUTE_TYPE", "float16"),
        "exe": cfg.get("WHISPER_CTRANSLATE2_EXE", ""),
        "model_dir": cfg.get("WHISPER_MODEL_DIR", ""),
        "model_cache_dir": cfg.get("WHISPER_MODEL_CACHE_DIR", ""),
        "local_files_only": cfg.get("WHISPER_LOCAL_FILES_ONLY", "").lower() == "true"
                          or bool(cfg.get("WHISPER_MODEL_DIR")),
    }


# ========================================================================
# .env 写入
# ========================================================================

def _key_to_dotenv(key: str) -> str:
    """将内部键名转为 .env 键名。"""
    mapping = {
        "whisper.model": "WHISPER_MODEL",
        "whisper.language": "WHISPER_LANGUAGE",
        "whisper.device": "WHISPER_DEVICE",
        "whisper.compute_type": "WHISPER_COMPUTE_TYPE",
        "whisper.exe": "WHISPER_CTRANSLATE2_EXE",
        "whisper.model_dir": "WHISPER_MODEL_DIR",
        "whisper.model_cache_dir": "WHISPER_MODEL_CACHE_DIR",
        "whisper.local_files_only": "WHISPER_LOCAL_FILES_ONLY",
        "api.key": "API_KEY",
        "api.url": "API_URL",
        "api.model": "MODEL_NAME",
        "api.provider": "API_PROVIDER",
        "ffmpeg.path": "FFMPEG_PATH",
    }
    if key in mapping:
        return mapping[key]
    # 原样返回大写
    return key.upper().replace(".", "_")


# 可配置的键及其默认值
WHISPER_SETTINGS = {
    "whisper.model": ("medium", "模型大小: tiny/base/small/medium/large"),
    "whisper.language": ("zh", "转写语言: zh/en/ja/auto"),
    "whisper.device": ("cuda", "转写设备: cuda/cpu"),
    "whisper.compute_type": ("float16", "计算精度: float16/int8/float32"),
}

API_SETTINGS = {
    "api.key": ("", "API 密钥"),
    "api.url": ("https://api.deepseek.com/v1/chat/completions", "API 地址"),
    "api.model": ("deepseek-chat", "模型名称"),
    "api.provider": ("deepseek", "API 提供商"),
}

ALL_SETTINGS = {}
ALL_SETTINGS.update(WHISPER_SETTINGS)
ALL_SETTINGS.update(API_SETTINGS)


def config_get(key: str, config: Optional[dict] = None) -> str:
    """获取单个配置项的值。"""
    cfg = config or load_env()
    env_key = _key_to_dotenv(key)
    val = cfg.get(env_key, "")
    if not val and key in ALL_SETTINGS:
        val = ALL_SETTINGS[key][0]
    return val


def config_set(key: str, value: str) -> str:
    """设置单个配置项并写入 .env 文件。

    Returns:
        配置项的 .env 键名
    """
    env_path = _get_env_path()
    env_key = _key_to_dotenv(key)
    new_line = f"{env_key}={value}"

    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                new_lines.append(line)
                continue
            k, _, _ = stripped.partition("=")
            if k.strip() == env_key:
                new_lines.append(new_line)
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(new_line)
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(f"{new_line}\n", encoding="utf-8")

    return env_key


def config_list() -> list[dict]:
    """列出所有可配置项及其当前值。"""
    cfg = load_env()
    result = []
    for key, (default, desc) in {**WHISPER_SETTINGS, **API_SETTINGS}.items():
        env_key = _key_to_dotenv(key)
        current = cfg.get(env_key, "")
        result.append({
            "key": key,
            "env_key": env_key,
            "value": current or default,
            "default": default,
            "description": desc,
            "is_set": bool(current),
        })
    return result
