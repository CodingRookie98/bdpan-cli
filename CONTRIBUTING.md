# Contributing to bdpan-cli (贡献指南)

感谢你关注并参与 `bdpan-cli` 的建设！我们欢迎社区提交 Issue、反馈缺陷或发起 Pull Request。

---

## 1. 行为守则与核心军规

参与本项目开发须严格遵守以下原则：
- **网盘资产安全与对账守恒**：涉及文件批量更名、移动、去重或删除的操作，严禁未经预演（`--dry-run`）直接执行不可逆操作；
- **测试驱动与全绿门禁**：任何代码提交必须配备单元测试，全量测试套件必须保持 100% 通过（`Exit Code 0`），测试用例数量只增不减；
- **文档与代码伴随更新**：变更命令行参数、接口定义或行为契约时，必须联动更新 `README.md`、`docs/` 及 `changelog.md`。

---

## 2. 本地开发环境搭建

本项目采用现代 Python 包管理工具 `uv`（Python >= 3.12）。

### 2.1 克隆仓库与安装依赖
```bash
git clone https://github.com/CodingRookie98/bdpan-cli.git
cd bdpan-cli

# 安装并同步开发依赖
uv sync
```

### 2.2 本地运行与调试
```bash
# 执行 CLI 命令
uv run bdpan --help

# 查询网盘配额（需配置 .env 凭据）
uv run bdpan quota
```

---

## 3. 测试与代码质量门禁

提交 PR 前必须执行以下完整测试与静态语法检查：

### 3.1 语法检查 (L0)
```bash
uv run python -m compileall -q src tests
```

### 3.2 单元测试全绿 (L1)
由于部分全局开发环境（如 ROS Jazzy）可能注入额外的 pytest 钩子，推荐在运行测试时增加环境变量保护：
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest
```

### 3.3 文档门禁审计 (Docs-as-Code)
涉及文档变动时，必须运行文档自动化门禁脚本：
```bash
python3 scripts/check-doc-links.py --root docs
python3 scripts/trim-revision.py --root docs --fix --keep 5
python3 scripts/generate-llms-txt.py --root docs --output docs/llms.txt
```

---

## 4. 提交信息规范 (Conventional Commits)

提交记录必须遵循规范化格式：
- `feat(scope): 描述新功能`（如 `feat(download): add chunked download engine`）
- `fix(scope): 修复缺陷`（如 `fix(scraper): resolve title truncation on 4K tag`）
- `docs(scope): 文档变动`（如 `docs(project): update roadmap for phase 1`）
- `refactor(scope): 重构但无行为改变`
- `test(scope): 增加或调整测试用例`

---

## 5. 打包构建与验证

验证标准打包产物是否符合 PyPI 规范：
```bash
# 构建源码包与 Wheel
uv build

# 检查产物
ls -lh dist/
```
