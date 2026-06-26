# media2md-player

音视频 → 文稿 → AI 修正 → 导读 → Markdown 导出一体化工具。

## 功能

- **字幕提取**：优先提取视频内嵌字幕，也支持外部 `.srt`/`.vtt` 文件
- **Whisper 转写**：无字幕时自动调用本地 Whisper 生成带时间戳的文稿
- **AI 修正**：调用 DeepSeek/Kimi 等 API 修正 Whisper 同音字/实体错误
- **导读生成**：基于文稿生成结构化导读（核心观点、场景建议、行动步骤等）
- **Markdown 导出**：文稿 + 修正版 + 导读，三者分开导出
- **GUI 播放器**：PyQt6 桌面应用，视频播放 + 时间戳点击跳转 + 文稿高亮跟踪

## 快速开始

```bash
# 克隆项目
git clone <repo-url>
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

# 启动 GUI 播放器（需要额外安装 PyQt6）
pip install -e ".[gui]"
media2md-gui
```

## 命令参考

| 命令 | 用途 |
|---|---|
| `media2md process <file>` | 全流程：转写→修正→导读→导出 |
| `media2md transcribe <file>` | 仅转写 |
| `media2md correct <file>` | 仅 AI 修正 |
| `media2md guide <file>` | 仅生成导读 |
| `media2md setup` | 初始化环境（安装 Whisper + 下载模型） |
| `media2md setup --check` | 检测环境状态 |
| `media2md config` | 查看所有配置 |
| `media2md config <key> <value>` | 修改配置 |
| `media2md-gui` | 启动图形界面 |

## 项目结构

```
media2md-player/
├── media2md/           # 核心 Python 包
│   ├── cli/            # CLI 入口
│   ├── pipeline/       # 处理管线
│   ├── models/         # 数据模型
│   └── utils/          # 工具函数
├── gui/                # PyQt6 GUI（开发中）
├── tests/              # 测试
├── data/               # 示例数据
└── process/            # 运行时工作目录
```

## 许可证

MIT
