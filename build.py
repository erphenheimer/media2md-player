"""
media2md-player 打包脚本
用法: python build.py
"""
import subprocess
import os
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")

PROJECT = Path(__file__).parent
PYTHON = str(PROJECT / ".venv" / "Scripts" / "python.exe")

HIDDEN = [
    "--hidden-import", "media2md",
    "--hidden-import", "media2md.cli.main",
    "--hidden-import", "media2md.models.transcript",
    "--hidden-import", "media2md.models.guide",
    "--hidden-import", "media2md.pipeline.extractor",
    "--hidden-import", "media2md.pipeline.transcriber",
    "--hidden-import", "media2md.pipeline.corrector",
    "--hidden-import", "media2md.pipeline.guide_generator",
    "--hidden-import", "media2md.pipeline.exporter",
    "--hidden-import", "media2md.pipeline.orchestrator",
    "--hidden-import", "media2md.pipeline.setup",
    "--hidden-import", "media2md.utils.config",
    "--hidden-import", "media2md.utils.timestamp",
    "--hidden-import", "media2md.utils.subtitle_parser",
]

BASE = [
    "--noconfirm", "--clean",
    "--paths", str(PROJECT),
    "--specpath", str(PROJECT / "build" / "spec"),
    "--workpath", str(PROJECT / "build" / "work"),
]


def run_build(name, entry, extra_hidden=None):
    output = PROJECT / "dist" / name
    cmd = [
        PYTHON, "-m", "PyInstaller",
        "--name", name,
        "--onefile",
        "--distpath", str(output),
    ] + BASE + HIDDEN
    if extra_hidden:
        cmd += extra_hidden
    cmd.append(str(entry))

    print(f"[BUILD] {name}...")
    result = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        err = result.stderr[-800:] if result.stderr else "unknown error"
        print(f"[FAIL] {name}: {err}")
        return False
    exe = output / f"{name}.exe"
    if exe.exists():
        size = exe.stat().st_size / 1024 / 1024
        print(f"[OK] {name}.exe ({size:.1f} MB)")
        return True
    print(f"[FAIL] {name}.exe not found")
    return False


if __name__ == "__main__":
    ok = True
    ok &= run_build("media2md", PROJECT / "media2md" / "cli" / "main.py")
    ok &= run_build("media2md-gui", PROJECT / "gui" / "__main__.py", extra_hidden=[
        "--hidden-import", "PyQt6",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtMultimedia",
        "--hidden-import", "PyQt6.QtMultimediaWidgets",
    ])
    print()
    if ok:
        print("[DONE] Both packages ready!")
        print(f"  CLI: {PROJECT / 'dist' / 'media2md' / 'media2md.exe'}")
        print(f"  GUI: {PROJECT / 'dist' / 'media2md-gui' / 'media2md-gui.exe'}")
    else:
        print("[WARN] Some builds failed")
