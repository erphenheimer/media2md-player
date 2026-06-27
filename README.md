# media2md-player

🎬 **音视频 + 字幕 → 智能文稿 + 结构化导读** 一体化工

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub Release](https://img.shields.io/github/v/release/erphenheimer/media2md-player)](https://github.com/erphenheimer/media2md-player/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org)

📥 **免安装下载**：[Releases 页面](https://github.com/erphenheimer/media2md-player/releases) 提供打包好的 `.exe`，双击即用。

## ✨ 功能

| 模块 | 说明 |
|---|---|
| **📂 字幕提取** | 优先提取视频内嵌字幕，也支持外部 `.srt`/`.vtt`/`.ass` 文件 |
| **🎙️ 语音转写** | 无字幕时自动调用本地 Whisper 生成带时间戳的文稿，支持 CUDA/CPU |
| **✏️ AI 修正** | 调用 DeepSeek / Kimi / OpenAI API 修正 Whisper 同音字、实体、标点错误 |
| **📖 生成导读** | 基于文稿生成结构化导读：一句话结论 / 核心观点 / 关键词 / 场景建议 / 行动步骤 |
| **💾 导出文稿** | 原始文稿、AI 修正版、导读三者分开导出为 Markdown，按源文件分文件夹 |
| **🖥️ GUI 桌面应用** | 暗色主题播放器 + 侧边栏标签页 + 集成设置面板，时间戳高亮跟踪 |

## 🚀 快速开始

### 方式一：下载打包好的 exe（推荐）

1. 打开 [Releases 页面](https://github.com/erphenheimer/media2md-player/releases)
2. 下载 `media2md-gui.exe`（桌面版）或 `media2md.exe`（命令行版）
3. 双击运行
4. 首次使用 → 点 **设置 → 初始化转写环境**，自动下载 Whisper 模型

> 命令行版用法：打开终端运行 `media2md.exe process video.mp4 --output ./output`

### 方式二：从源码安装

```bash
# 克隆项目
git clone https://github.com/erphenheimer/media2md-player.git
cd media2md-player

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装基础依赖
pip install -e .

# 配置 API（修正和导读需要 DeepSeek/Kimi API Key）
cp .env.example .env
# 编辑 .env 填入 API_KEY 等配置

# 初始化 Whisper 环境（自动安装 whisper-ctranslate2 + 下载模型）
media2md setup

# 配置转写参数（可选）
media2md config whisper.device cpu          # 使用 CPU 转写
media2md config whisper.model tiny          # 使用 tiny 模型（更快）
media2md config                             # 查看所有配置
media2md setup --check                      # 检测环境

# 处理单个文件
media2md process video.mp4 --output ./output

# 启动 GUI 桌面应用（需要额外安装 PyQt6）
pip install -e ".[gui]"
media2md-gui
```

## 📖 CLI 命令参考

| 命令 | 用途 |
|---|---|
| `media2md process <file>` | 全流程：字幕提取 → 转写 → 修正 → 导读 → 导出 |
| `media2md transcribe <file>` | 仅转写（Whisper） |
| `media2md correct <file>` | 仅 AI 修正文稿 |
| `media2md guide <file>` | 仅生成导读 |
| `media2md export <file>` | 仅导出 Markdown |
| `media2md setup` | 一键初始化环境（安装 Whisper + 下载模型） |
| `media2md setup --check` | 检测环境状态 |
| `media2md config` | 查看所有配置项 |
| `media2md config <key> <value>` | 修改配置项 |

## 🖥️ GUI 桌面应用

![GUI 截图](https://via.placeholder.com/800x450/252525/cccccc?text=media2md-player+GUI)

- **暗色主题**：护眼深色界面
- **侧边栏**：快速切换「文稿 / 修正版 / 导读 / 设置」标签页
- **视频播放器**：播放/暂停、进度条拖动、时间显示
- **时间戳高亮**：播放时自动高亮当前段落，点击段落可跳转
- **内嵌操作按钮**：🎙️ 语音转写 / ✏️ AI 修正 / 📖 生成导读 / 💾 导出文稿
- **集成设置面板**：Whisper 模型大小、设备、语言、API 配置一键可调

## 📂 项目结构

```
media2md-player/
├── media2md/           # 核心 Python 包
│   ├── cli/            # CLI 入口（main.py）
│   ├── pipeline/       # 处理管线（extractor/transcriber/corrector/guide/exporter）
│   ├── models/         # 数据模型（transcript/guide）
│   └── utils/          # 工具函数（config/subtitle_parser/timestamp）
├── gui/                # PyQt6 桌面应用
│   ├── main_window.py  # 主窗口（播放器+文稿面板+设置）
│   └── __init__.py
├── tests/              # 测试用例
├── data/sample/        # 示例数据
├── dist/               # PyInstaller 打包输出
├── build.py            # 打包脚本（生成独立 exe）
├── pyproject.toml      # 项目配置
└── CHANGELOG.md        # 版本更新日志
```

## 🔧 打包

```bash
# 在本地生成 exe（需要已安装 PyQt6）
python build.py
# 输出: dist/media2md/media2md.exe
#       dist/media2md-gui/media2md-gui.exe
```

## 📜 版本历史

详见 [CHANGELOG.md](./CHANGELOG.md)

| 版本 | 亮点 |
|---|---|
| v0.1.1 | GUI 按钮加中文标签、首次使用引导、CHANGELOG |
| v0.1.0 | 首个公开发布版本 |

## 📄 许可证

GNU General Public License v3.0
