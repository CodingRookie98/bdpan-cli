# bdpan-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

百度网盘工程化 CLI 管理工具。基于[百度网盘开放平台](https://pan.baidu.com/union/doc/)官方 SDK 与协议标准构建，提供文件管理、分片上传续传、冲突副本治理与影视媒体库规范化自动化刮削整理。

---

## 快速安装 (Installation)

### 方式 1：uv tool 安装（推荐，隔离环境）
```bash
uv tool install bdpan-cli
```

### 方式 2：即用即走（无需预先安装）
```bash
uvx bdpan-cli --help
```

### 方式 3：传统 pip 安装
```bash
pip install bdpan-cli
```

### 方式 4：跨平台单文件二进制（免 Python 运行时）
前往 [GitHub Releases](https://github.com/CodingRookie98/bdpan-cli/releases) 直接下载对应平台单文件二进制可执行包，加入 `PATH` 即可运行：
- `bdpan-linux-amd64`
- `bdpan-linux-arm64`
- `bdpan-macos-arm64` (Apple Silicon)
- `bdpan-macos-x86_64` (Intel)
- `bdpan-windows-amd64.exe`

---

## 命令行使用 (CLI)

```bash
# 查看帮助
bdpan --help

# 常用命令
bdpan ls /影视/电影
bdpan mkdir /新目录
bdpan mv <源路径>... <目标目录>          # 多源时目标须为已存在目录（自动记录流水）
bdpan cp <源路径>... <目标目录|目标目录/新名>  # 单源支持改名
bdpan rename <路径> <新名称>              # 原地更名（自动记录流水）
bdpan rm <路径>... [-y]
bdpan quota [--check-expire] [--check-free]  # 网盘容量
bdpan whoami                             # 账户信息
bdpan search <关键词> [--dir 目录] [--no-recursion]
bdpan tree <路径> [--depth N] [--index 索引.json]  # 递归树+本地索引
bdpan upload <本地文件> <目标目录|目标目录/新名> [--overwrite]  # 分片上传+断点续传（首片秒传+动态机房）
bdpan download <网盘文件>... [--dest 本地目录] [--overwrite]  # 大文件断点续传下载
bdpan dlink <网盘文件>... [--aria2 | --curl]          # 提取高速直链或导出下载脚本
bdpan dedup /影视/电影 --staging-dir /隔离区      # 治理 (1)/(2) 冲突副本
bdpan scrape foldering /影视/电影/unscraped       # 媒体库电影散落文件建目录归集

# 安全运维体系与操作撤销 (Safety & Undo)
bdpan ops list [--limit 20]               # 查看关键变更操作流水审计日志
bdpan ops show <op_id>                    # 查看某次操作的明细与映射清单
bdpan undo <op_id> [--dry-run] [-y]       # 逆向撤销回滚指定批次操作（支持预演）

# 多账号认证与隔离 (Multi-Account Auth)
bdpan auth list                           # 查看本地保存的网盘账号及凭证有效性
bdpan auth switch <alias>                 # 切换当前默认活跃账号
bdpan auth login [--account <alias>]      # 登录/重新授权指定账号别名
bdpan --account <alias> <subcommand>      # 临时以指定账号执行单次命令（多租户并发隔离）

# 媒体可观测性与全局 JSON 信封 (Media Insights & JSON)
bdpan info /影视/电影/Inception.mkv        # 探测视频精准分辨率(4K/1080P)、时长、HEVC编码与音轨
bdpan stats /影视/电影 [--depth N]        # 递归聚合统计目录总容量、总文件数及媒体格式分类占比
bdpan --json <subcommand>                 # 所有核心查询命令支持标准化 JSON 信封输出（脚本化集成）

# AI 原生集成 (Model Context Protocol / MCP)
bdpan mcp                                 # 启动标准 stdio MCP Server，供 Claude Code / Cursor / AI 智能体调用
```

> **操作安全机制**：`mv` / `cp` 遵循严格目标判定；`rm` 默认交互确认，`-y` 跳过；网盘删除由服务端移入回收站。批量操作支持 `--dry-run` 预演；所有破坏性移动更名自动落盘流水审计，支持一键逆向回滚还原。

---

## 本地开发环境

```bash
# 克隆仓库
git clone https://github.com/CodingRookie98/bdpan-cli.git
cd bdpan-cli

# 安装依赖
uv sync

# 本地调试运行
uv run bdpan --help

# 运行全量测试
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest
```

## 应用凭证配置

复制模板并填入开放平台应用的 AppKey / AppSecret（`.env` 已被 git 忽略，不会提交）：

```bash
cp .env.example .env
```

---

## 项目结构

```
├── docs/                     # 治理文档（Diátaxis 四象限，见 docs/GOVERNANCE.md）
│   ├── index.md              # 知识库总入口
│   ├── llms.txt              # AI 智能体机器地图
│   ├── project/              # 演进路线图 (roadmap.md)、待办 (backlog.md)、计划 (plans/)
│   └── reference/api/        # SDK 接口参考（机器真理源）
├── pyproject.toml            # 标准 Python 项目配置与 CLI 命令行入口
├── src/bdpan_cli/            # 核心业务代码与 CLI 子命令
│   └── _vendor/              # 内聚内嵌的 OpenAPI Client 依赖包（标准轮子直接打包）
├── tests/                    # 单元测试与回归套件 (170+ 项全绿)
└── .python-version           # 3.12
```

## 贡献与开源

详细贡献规范、测试门禁与提交信息格式见 [CONTRIBUTING.md](./CONTRIBUTING.md)。开源许可协议遵循 [MIT License](./LICENSE)。
