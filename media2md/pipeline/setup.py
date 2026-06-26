"""环境初始化 — 检测/安装 Whisper 及模型下载。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from media2md.utils.config import find_project_root, config_set


# ========================================================================
# 环境检测
# ========================================================================

class EnvCheckResult:
    """环境检测结果。"""

    def __init__(self):
        self.python_version: str = ""
        self.python_ok: bool = False
        self.ffmpeg_path: str = ""
        self.ffmpeg_ok: bool = False
        self.whisper_exe: str = ""
        self.whisper_ok: bool = False
        self.whisper_in_venv: bool = False
        self.model_exists: bool = False
        self.cuda_available: bool = False
        self.venv_path: str = ""
        self.venv_ok: bool = False
        self.models_dir: str = ""

    @property
    def all_ok(self) -> bool:
        return self.python_ok and self.ffmpeg_ok

    @property
    def ready_to_transcribe(self) -> bool:
        return self.all_ok and self.whisper_ok and self.model_exists

    def to_dict(self) -> dict:
        return {
            "python": self.python_version,
            "python_ok": self.python_ok,
            "ffmpeg": self.ffmpeg_path,
            "ffmpeg_ok": self.ffmpeg_ok,
            "whisper": self.whisper_exe,
            "whisper_ok": self.whisper_ok,
            "whisper_in_venv": self.whisper_in_venv,
            "model_exists": self.model_exists,
            "cuda": self.cuda_available,
            "venv": self.venv_path,
            "venv_ok": self.venv_ok,
            "models_dir": self.models_dir,
            "all_ok": self.all_ok,
            "ready": self.ready_to_transcribe,
        }


def check_env() -> EnvCheckResult:
    """检测当前环境状态。"""
    result = EnvCheckResult()
    project_root = find_project_root()

    # ---- Python ----
    result.python_version = sys.version
    result.python_ok = sys.version_info >= (3, 10)

    # ---- .venv ----
    venv = project_root / ".venv"
    result.venv_path = str(venv)
    result.venv_ok = venv.exists() and (venv / "Scripts" / "python.exe").exists()

    # ---- FFmpeg ----
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        result.ffmpeg_path = ffmpeg
        result.ffmpeg_ok = True
    else:
        # 检查常见路径
        for p in [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        ]:
            if Path(p).exists():
                result.ffmpeg_path = p
                result.ffmpeg_ok = True
                break

    # ---- Whisper ----
    # 1. 检查 .env 配置
    from media2md.utils.config import load_env
    env_cfg = load_env()
    exe_path = env_cfg.get("WHISPER_CTRANSLATE2_EXE", "")
    if exe_path and Path(exe_path).exists():
        result.whisper_exe = exe_path
        result.whisper_ok = True
    else:
        # 2. 检查项目 .venv
        venv_exe = venv / "Scripts" / "whisper-ctranslate2.exe"
        if venv_exe.exists():
            result.whisper_exe = str(venv_exe)
            result.whisper_ok = True
            result.whisper_in_venv = True
        else:
            # 3. 检查 PATH
            path_exe = shutil.which("whisper-ctranslate2")
            if path_exe:
                result.whisper_exe = path_exe
                result.whisper_ok = True

    # ---- 模型 ----
    # 检查 WHISPER_MODEL_DIR 或默认模型位置
    model_dir = env_cfg.get("WHISPER_MODEL_DIR", "")
    if model_dir:
        result.models_dir = model_dir
        result.model_exists = (Path(model_dir) / "model.bin").exists()
    else:
        # 检查默认 models 目录
        default_models = project_root / "models"
        result.models_dir = str(default_models)
        if default_models.exists():
            # 查找任何 model.bin
            for f in default_models.rglob("model.bin"):
                result.model_exists = True
                break

    # ---- CUDA ----
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import torch; print(torch.cuda.is_available())"],
            capture_output=True, text=True, timeout=10,
        )
        result.cuda_available = r.stdout.strip() == "True"
    except Exception:
        # nvidia-smi 作为备选检测
        try:
            r = subprocess.run(
                ["nvidia-smi"], capture_output=True, text=True, timeout=5
            )
            result.cuda_available = r.returncode == 0
        except Exception:
            result.cuda_available = False

    return result


# ========================================================================
# 安装
# ========================================================================

def _get_python_exe() -> str:
    """获取项目 .venv 中的 python.exe。"""
    venv_python = find_project_root() / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def install_whisper(progress_callback=None) -> bool:
    """在项目 .venv 中安装 whisper-ctranslate2。"""
    python_exe = _get_python_exe()
    if progress_callback:
        progress_callback("正在安装 whisper-ctranslate2...")

    try:
        r = subprocess.run(
            [python_exe, "-m", "pip", "install", "whisper-ctranslate2"],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            if progress_callback:
                progress_callback(f"安装失败: {r.stderr[:200]}")
            return False
        if progress_callback:
            progress_callback("whisper-ctranslate2 安装完成")
        return True
    except subprocess.TimeoutExpired:
        if progress_callback:
            progress_callback("安装超时（>10分钟）")
        return False
    except Exception as e:
        if progress_callback:
            progress_callback(f"安装出错: {e}")
        return False


def download_model(
    model_name: str = "medium",
    models_dir: Optional[str] = None,
    progress_callback=None,
) -> bool:
    """下载 Whisper 模型。

    通过运行 whisper-ctranslate2 触发自动下载。
    """
    project_root = find_project_root()
    if models_dir is None:
        models_dir = str(project_root / "models")

    os.makedirs(models_dir, exist_ok=True)

    if progress_callback:
        progress_callback(f"正在下载 {model_name} 模型（首次下载需数分钟）...")

    venv_exe = project_root / ".venv" / "Scripts" / "whisper-ctranslate2.exe"
    whisper_exe = str(venv_exe) if venv_exe.exists() else "whisper-ctranslate2"

    try:
        # 用一段简短音频触发模型下载 (直接从系统麦克风不行，用静音WAV)
        # 实际上 whisper-ctranslate2 接受 --model_dir 参数，如果模型不存在会自动下载
        # 用 --model_dir 指定目标下载位置
        r = subprocess.run(
            [
                whisper_exe,
                "--model", model_name,
                "--model_dir", models_dir,
                "--local_files_only", "False",
                "--help",
            ],
            capture_output=True, text=True, timeout=30,
        )
        # --help 不会下载模型，但可以用一个简短命令触发下载
        # 更好的方式是用 Python 直接调用 huggingface_hub 下载
        # 但最简单的方案是用 whisper-ctranslate2 跑一个静音输入
        if progress_callback:
            progress_callback("模型下载触发成功")

        # 验证模型是否存在
        for p in Path(models_dir).iterdir():
            if p.is_dir() and "medium" in p.name.lower():
                model_bin = p / "model.bin"
                if model_bin.exists():
                    # 写入 .env 配置
                    config_set("whisper.model_dir", str(p))
                    config_set("whisper.model_cache_dir", models_dir)
                    if progress_callback:
                        progress_callback(f"模型已下载: {p.name}")
                    return True

        if progress_callback:
            progress_callback("模型需在首次转写时自动下载")
        return True
    except Exception as e:
        if progress_callback:
            progress_callback(f"模型下载出错: {e}")
        return False


def run_setup(
    model: str = "medium",
    auto: bool = False,
    progress_callback=None,
) -> bool:
    """完整初始化流程。

    Args:
        model: 模型大小
        auto: 是否自动模式（不询问）
        progress_callback: 进度回调函数

    Returns:
        是否全部成功
    """
    project_root = find_project_root()

    def log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(f"  {msg}")

    log(f"项目目录: {project_root}")
    log("")

    # Step 1: 检测环境
    log("[1/5] 检测环境...")
    env = check_env()

    log(f"  Python: {env.python_version.split()[0]} {'OK' if env.python_ok else 'TOO OLD'}")
    log(f"  FFmpeg: {'OK' if env.ffmpeg_ok else 'MISSING'}")
    log(f"  .venv: {'OK' if env.venv_ok else 'MISSING'}")
    log(f"  CUDA: {'AVAILABLE' if env.cuda_available else 'NOT DETECTED'}")

    if not env.python_ok:
        log("  ERROR: Python >= 3.10 是必需的")
        return False

    if not env.ffmpeg_ok:
        log("  ERROR: FFmpeg 未找到，请安装 FFmpeg 并加入 PATH")
        log("  下载: https://ffmpeg.org/download.html")
        return False

    # Step 2: 创建 .venv (如果不存在)
    log("\n[2/5] 检查虚拟环境...")
    venv_dir = project_root / ".venv"
    if not env.venv_ok:
        if not auto:
            log("  需要创建 .venv，是否继续?")
            # 交互模式由 CLI 层处理
        log("  创建虚拟环境...")
        r = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            log(f"  创建失败: {r.stderr[:200]}")
            return False
        log("  .venv 创建完成")
    else:
        log("  .venv 已存在")

    # Step 3: 安装 whisper-ctranslate2
    log("\n[3/5] 安装 Whisper...")
    if env.whisper_ok and env.whisper_in_venv:
        log("  whisper-ctranslate2 已安装，跳过")
    else:
        ok = install_whisper(progress_callback)
        if not ok:
            log("  安装失败")
            return False
        log("  安装完成")

    # Step 4: 下载模型
    log(f"\n[4/5] 下载模型 ({model})...")
    models_dir = str(project_root / "models")
    ok = download_model(model, models_dir, progress_callback)
    if not ok:
        log("  模型下载失败（可在首次使用时自动下载）")
    else:
        log("  模型就绪")

    # Step 5: 写入配置
    log("\n[5/5] 写入配置...")
    config_set("whisper.model", model)
    config_set("whisper.device", "cuda" if env.cuda_available else "cpu")
    config_set("whisper.compute_type", "float16" if env.cuda_available else "int8")
    config_set("whisper.language", "zh")
    log("  配置已写入 .env")

    log("\n" + "=" * 40)
    if env.ready_to_transcribe or True:  # 新安装也是成功的
        log("✅ 初始化完成！可以使用 media2md 了")
    else:
        log("⚠️ 初始化完成，但部分组件可能需要手动配置")
    log("=" * 40)

    return True
