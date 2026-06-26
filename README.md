# media2md-player

音视频 → 文稿 → AI 修正 → 导读 → Markdown 导出一体化工具。

## 功能

- **字幕提取**：优先提取视频内嵌字幕，也支持外部 `.srt`/`.vtt` 文件
- **Whisper 转写**：无字幕时自动调用本地 Whisper 生成带时间戳的文稿
- **AI 修正**：调用 DeepSeek/Kimi 等 API 修正 Whisper 同音字/实体错误
- **导读生成**：基于文稿生成结构化导读（核心观点、场景建议、行动步骤等）
- **Markdown 导出**：文稿 + 修正版 + 导读，三者分开导出
- **GUI 播放器**（开发中）：视频播放 + 时间戳点击跳转

## 快速开始

```bash
# 克隆项目
git clone <repo-url>
cd media2md-player

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -e .

# 配置 API（修正和导读需要）
cp .env.example .env
# 编辑 .env 填入 API_KEY 等配置

# 处理单个文件
media2md process video.mp4 --output ./output
```

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
