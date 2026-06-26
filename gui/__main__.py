"""media2md-player GUI 启动入口。"""
import sys
import os
from pathlib import Path

# 确保项目根在 Python 路径中
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from gui.main_window import main

if __name__ == "__main__":
    main()

