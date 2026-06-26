# Contributing to media2md-player

感谢你愿意为这个项目贡献代码！

## 开发环境

```bash
git clone <repo-url>
cd media2md-player
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[gui]"
```

## 代码规范

- Python 3.10+
- 遵循 PEP 8
- 类型注解（type hints）是必须的
- 中文注释和文档字符串

## Git 规范

- 提交信息格式：`type: 简短描述`
  - `feat:` 新功能
  - `fix:` Bug 修复
  - `refactor:` 重构
  - `style:` 界面/样式调整
  - `docs:` 文档
- 每个提交保持原子性（一个改动一个提交）

## PR 流程

1. Fork 项目
2. 创建功能分支：`git checkout -b feat/xxx`
3. 提交代码
4. 确保 `python build.py` 能通过
5. 发起 Pull Request

## 打包

```bash
python build.py
```

产出在 `dist/` 目录。
