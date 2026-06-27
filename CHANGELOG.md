# Changelog

## v0.1.1 (2026-06-26)

### 🎨 用户体验优化

- **GUI 按钮**：从纯图标改为「图标 + 中文标签」，功能一目了然
  - `🎙️` → `🎙️ 语音转写`
  - `✏️` → `✏️ AI 修正`
  - `📖` → `📖 生成导读`
  - `💾` → `💾 导出文稿`
- **按钮 Tooltip**：补充详细说明，鼠标悬停即知用途
- **打开文件按钮**：改为「📂 打开文件...」，附带支持格式说明
- **首次使用引导**：GUI 无 Whisper 时弹出引导窗口，指引运行 `media2md setup`

### 🐛 问题修复

- **GUI 闪退修复**：`_on_transcribe_done` 不再重复调用 `_on_task_finished`，避免双重清理崩溃
- **音频文件支持**：`extractor.py` 补全音频文件的外部字幕查找路径
- **无声音修复**：`gui/main_window.py` 补充 `QAudioOutput` 绑定（Qt6 必需）
- **GBK 编码崩溃**：`subprocess.run` 添加 `errors="replace"` 防止非 UTF-8 输出崩溃

### 🚀 新增功能

- **`media2md setup` 命令**：一键安装 Whisper + 下载模型 + 配置环境
- **`media2md config` 命令**：查看/修改配置项（model/language/device/compute_type）
- **GUI 设置面板**：Whisper 参数可调（模型大小/设备/精度/语言）
- **GUI 侧边栏**：快速切换文稿/修正版/导读/设置标签页

### 🔧 技术改进

- **移除硬编码路径**：`transcriber.py` 不再写死 ACER 机器路径，改为 `.env` → 项目 `.venv` → `PATH` 通用链路
- **`pyproject.toml`**：新增 `media2md-gui` 和 `media2md-config` 入口点
- **`.env.example`**：补全 Whisper 配置项说明

## v0.1.0 (2026-06-26)

### 🎉 首个公开发布版本

#### 核心功能

- **CLI 管线**：`media2md process` — 全流程处理（提取 → 转写 → 修正 → 导读 → 导出）
- **GUI 桌面应用**：暗色主题，视频播放器 + 文稿面板 + 集成设置
- **字幕提取**：支持 SRT/VTT/ASS 解析，ffmpeg 内嵌字幕提取
- **Whisper 转写**：whisper-ctranslate2 集成，支持 CUDA/CPU
- **AI 文稿修正**：DeepSeek / OpenAI / Kimi API 自动纠错
- **智能导读生成**：一句话结论 / 核心观点 / 关键词 / 场景建议 / 行动步骤
- **Markdown 导出**：按源文件分文件夹组织

#### 工程化

- **一键初始化**：`media2md setup` 自动安装 Whisper + 下载模型
- **配置管理**：`.env` 文件配置 API 密钥、Whisper 参数等
- **PyInstaller 打包**：`build.py` 生成独立 exe
- **开源材料**：MIT License、CONTRIBUTING.md、ISSUE_TEMPLATE
