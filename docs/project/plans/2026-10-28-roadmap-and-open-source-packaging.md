# bdpan-cli 开源筹备、全渠道打包分发与能力补齐实施计划

> **文档控制信息**
> - **文档标识**: PLAN-OPENSOURCE-PACKAGING-2026
> - **当前版本**: V1.0.0
> - **文档所有者**: 主调度智能体
> - **生效日期**: 2026-10-28
> - **关联路线图**: [roadmap.md](../roadmap.md)

> **目标元数据**
> - **所属项目**: bdpan-cli
> - **执行通道**: Heavy Track（跨模块核心重构：构建系统、Vendor 依赖内联、CI/CD 流水线与核心传输命令扩展；遵循 dual-round-review 与 doc-governance）
> - **目标简述**: 解决本地相对依赖阻断，实现 PyPI (`pip` / `uv tool`) 与 GitHub Releases 跨平台单文件二进制一键分发；完成 GitHub 开源合规与工程化基建；补齐 `download`、秒传 `upload`、`ops undo` 撤销回滚与 `mcp` 等生产级能力。
> - **创建日期**: 2026-10-28
> - **计划负责人**: 主调度智能体（goal-loop）
> - **需求方**: 用户（项目所有者）
> - **批准人 (User Nod)**: 待确认（待本计划审阅后确认）
> - **批准基线**: main@`91e1d14`
> - **状态**: 草案审核中 (Draft Pending Review)
> - **隔离分支**: `feature/packaging-and-roadmap`
> - **临时 Scratchpad**: `.goal-loop/scratchpad.md`（已被 `.gitignore` 忽略）

> **唯一可读真相源声明**：本文件是当前目标的唯一人类可读真相源。本文件的复选框与下方检查点锚点必须与机器状态保持一致。

---

## 🚀 活跃执行状态与持久化检查点 (Active Checkpoint)
- **当前执行通道**: Heavy Track
- **当前活跃阶段**: P0 需求澄清与方案对齐（等待用户批准立项）
- **当前活跃子任务**: 计划文档制定与 Backlog 同步
- **当前子任务重试计数**: 0/3
- **外层循环迭代**: 0/5
- **最后一次验证状态**: Exit Code 0, 128 passed（main 分支全量测试套件全绿）
- **最新有效提交**: `91e1d14` (docs: update project backlog and changelog for BK-0028)
- **阻断原因**: 无

---

## 1. 目标范围与验收基线 (Scope & Acceptance Baseline)

### 1.0 验收口径 (Acceptance Criteria — 由需求方定义)
1. **打包与构建合规验收**：
   - 彻底移除 `pyproject.toml` 中的 `[tool.uv.sources]` 本地相对路径依赖；
   - 本地执行 `uv build` 成功生成标准 Python Wheel (`.whl`) 与源码包 (`.tar.gz`)，无任何外部私有依赖警告；
   - 在全新的虚拟环境中执行 `pip install dist/bdpan_cli-*.whl` 或 `uv tool install dist/bdpan_cli-*.whl`，可顺利安装并通过 `bdpan --help` 和 `bdpan whoami` 运行；
2. **二进制免环境分发验收**：
   - 本地基于 PyInstaller 或 CI 构建出针对当前系统架构的单文件二进制执行档 `dist/bdpan`；
   - 在无虚拟环境、未激活 Python 环境的独立目录下，直接 `./bdpan --version` 与 `./bdpan --help` 输出正常，零动态链接与外部路径缺失错误；
3. **开源工程与安全防线验收**：
   - 根目录具备合规的 `LICENSE` (MIT) 与 `CONTRIBUTING.md`；
   - CI 配置 `.github/workflows/ci.yml` 自动化运行测试；
   - 代码库中零真实 Token、零个人 AppKey 硬编码泄漏风险；
4. **核心能力补齐渐进式验收**：
   - 按照规划逐步实现 `download`、秒传 `upload`、`ops undo`、`mcp` 等子系统，每阶段保证新增单元测试全绿且不破坏既有 128 项测试资产。

---

## 2. 核心架构与技术选型裁决 (Architecture & Spike Decisions)

### 2.1 依赖架构：Vendor SDK 内联化方案 (Vendor Decoupling)
- **现状分析**：
  当前项目依赖 `vendor/baidu-pan-sdk`，源码在 `vendor/baidu-pan-sdk/openapi_client/`。
  `src/bdpan_cli/` 中的多处模块（如 `auth.py`, `file_manager.py`, `account.py`, `uploader.py` 等）直接 `import openapi_client`。
- **解耦决策**：
  - **短期方案（第一阶段实施）**：
    将 `vendor/baidu-pan-sdk/openapi_client` 完整迁移至 `src/bdpan_cli/_vendor/openapi_client`；
    在 `src/bdpan_cli/` 内部将 `import openapi_client` 规范替换为 `from bdpan_cli._vendor import openapi_client`；
    清理 `pyproject.toml` 中的 `dependencies = ["baidu-pan-sdk", ...]`，仅保留生产外部依赖 `["python-dotenv>=1.2.3"]`；
    移除 `[tool.uv.sources]` 配置块；
    在 `vendor/` 目录下保留原始上游镜像并注明来源，或者完全收敛进 `_vendor/`。
  - **收益**：立即具备标准 PyPI 发布能力，无需等待庞大 SDK 重写，成本最低、风险可控。

### 2.2 打包分发：PyInstaller 单文件跨平台二进制
- **构建选型**：使用 PyInstaller 配合 `entrypoint` 脚本进行打包；
- **核心命令示例**：
  ```bash
  uv run pyinstaller --onefile --name bdpan \
    --hidden-import bdpan_cli \
    --hidden-import bdpan_cli._vendor.openapi_client \
    src/bdpan_cli/cli.py
  ```
- **发布工作流 (GitHub Actions)**：
  - 利用 GitHub Actions 矩阵测试构建：`ubuntu-latest` (Linux x86_64), `windows-latest` (Windows x86_64), `macos-14` (macOS arm64 Apple Silicon), `macos-13` (macOS x86_64 Intel)；
  - 产出二进制自动归档至 Release Tag 的 Assets，供用户免安装直接下载。

---

## 3. 测试策略与质量裁定 (Testing Decision Matrix)

- **改动风险定级**: HIGH（涉及基础包结构调整、命名空间迁移与构建配置改动，属于骨干级别变更）
- **强制执行测试级别**:
  - [x] **L0 静态代码门禁**: `uv run python -m compileall src tests` 保证全量语法合规与 import 链路完整；
  - [x] **L1 单元测试套件**: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest` 保证既有 128 项单测全部全绿通过，并随新功能持续扩充；
  - [x] **L2 安装与隔离集成验证**:
    - 本地 `uv build` 打包；
    - 在纯净临时隔离环境安装生成的 wheel 文件并执行命令行验收测试；
    - 运行生成的二进制单文件执行档验证；
  - [x] **文档门禁 (Docs-as-Code)**: 零断链门禁脚本与 llms.txt 更新验证。

---

## 4. 分阶段实施工作包 (Phase Breakdown & Task Ledger)

### 阶段一：开源合规与全渠道打包分发基建 (Phase 1: Foundations & Packaging)
- [ ] **Task 1.1: Vendor 依赖内联化与构建解耦**
  - 将 `vendor/baidu-pan-sdk/openapi_client` 迁移至 `src/bdpan_cli/_vendor/openapi_client`；
  - 批量适配 `src/bdpan_cli/` 内部代码的引用路径，并确保 `tests/` 全部测试无需额外环境变量即可平稳导入；
  - 修改 `pyproject.toml`，移除 `baidu-pan-sdk` 外部依赖与 `[tool.uv.sources]`；
  - 运行全量测试套件确认 100% 通过（128 passed）。
- [ ] **Task 1.2: 标准 Wheel / Sdist 构建与纯净隔离安装实测**
  - 执行 `uv build` 输出 `dist/`；
  - 创建独立隔离临时环境，使用 `pip` 与 `uv tool` 试安装生成的 wheel，验证 `bdpan --version` 与子命令调用正常。
- [ ] **Task 1.3: 开源合规与工程化建设**
  - 创建 `LICENSE` (MIT) 文件；
  - 编写 `CONTRIBUTING.md`，规范化开源贡献流程与 TDD 指南；
  - 更新根目录 `README.md`，添加 PyPI 安装、二进制下载、多架构使用指引与配置指引；
  - 检查并巩固 `.gitignore`，严防任何 token 与 env 文件泄漏。
- [ ] **Task 1.4: 独立单文件二进制编译与 GitHub Actions 工作流设计**
  - 验证本地 PyInstaller 单文件二进制生成；
  - 编写 `.github/workflows/ci.yml`（PR/Push 矩阵自动化测试与静态检查）；
  - 编写 `.github/workflows/release.yml`（Tag 触发 PyPI 构建上传与跨平台二进制编译上传 Releases）。

---

### 阶段二：核心传输能力补齐与极速优化 (Phase 2: Core Transfer & Performance)
- [ ] **Task 2.1: 实现 `bdpan download` 下载引擎与断点续传**
  - 封装接口调用获取下载真实直链（`filemetas&dlink=1`）；
  - 注入 `User-Agent: pan.baidu.com` 请求头规避限速；
  - 实现基于 HTTP Range 的大文件并发分块下载与断点续传机制；
  - 编写单元测试（Mock HTTP 下载、分块与重试流）并对网盘小文件/大文件验证。
- [ ] **Task 2.2: 实现 `bdpan dlink` 直链与脚本导出命令**
  - 提供单文件/目录直链查询；
  - 输出配套 `aria2c` / `curl` 导出命令参数。
- [ ] **Task 2.3: 升级 `bdpan upload` 极速秒传机制**
  - 在上传预建阶段计算文件首片 256KB MD5 与全量 MD5；
  - 对接网盘秒传判定，命中时直接跳过分块传输完成创建；
  - 编写单测（Mock 秒传命中与未命中两种分支）。
- [ ] **Task 2.4: 接入 `locateupload` 动态最优机房探测**
  - 在分片上传前动态请求百度最优上传服务器节点 host，提升跨地域网络稳定性与上传吞吐量。

---

### 阶段三：安全运维体系与多账号隔离 (Phase 3: Safety Ops & Multi-Account)
- [ ] **Task 3.1: 构建 `.bdpan_ops` 操作流水审计子系统**
  - 设计结构化操作日志格式（包含操作唯一 ID、时间戳、命令名、操作人、源路径/目的路径映射清单）；
  - 在批量更名、批量移动、归集与去重命令中统一注入审计拦截器，原子落盘日志。
- [ ] **Task 3.2: 实现 `bdpan ops` 与 `bdpan undo` 可逆撤销命令**
  - 提供 `bdpan ops list` 与 `bdpan ops show <op_id>`；
  - 实现 `bdpan undo <op_id>`，自动解析操作对反向生成执行方案，支持 `--dry-run` 预览与一键复原；
  - 编写单元测试覆盖正向操作与逆向撤销的守恒对账。
- [ ] **Task 3.3: 多账号认证管理体系 (`bdpan auth`)**
  - 升级 `auth.py` TokenManager 支持多账号别名存储（如 `default`, `work`, `backup`）；
  - 增加 `bdpan auth list`、`bdpan auth add <alias>`、`bdpan auth switch <alias>`；
  - CLI 根命令新增全局 `--account <alias>` 参数支持即时切换。

---

### 阶段四：媒体可观测性与 AI/MCP 机器接入 (Phase 4: Media Insights & AI/MCP)
- [ ] **Task 4.1: 全局支持 `--json` 输出信封**
  - 设计统一的 JSON 响应格式规范；
  - 为所有子命令注入 `--json` 开关，方便自动化脚本与外部程序管道消费。
- [ ] **Task 4.2: 媒体元数据与目录聚合 (`bdpan info` & `bdpan stats`)**
  - 实现 `bdpan info` 查询媒体文件的编码、分辨率、时长等元数据；
  - 实现 `bdpan stats` 快速输出目录层级、文件数与容量分布。
- [ ] **Task 4.3: 原生 MCP Server 模式集成 (`bdpan mcp`)**
  - 引入 FastMCP 协议适配器，自省导出网盘 CLI 操作为标准 MCP 工具集；
  - 支持各类 AI 编程助手（Claude Code、Antigravity、Cursor）直接配置本 CLI 作为工具。

---

## 5. 阶段交付物清单与文档联动要求

1. **核心源码变更**:
   - `src/bdpan_cli/_vendor/` 内聚包
   - `src/bdpan_cli/download.py`（下载引擎）
   - `src/bdpan_cli/ops.py`（流水与撤销引擎）
   - `src/bdpan_cli/mcp_server.py`（MCP 服务端）
2. **打包与开源规范文件**:
   - `LICENSE`
   - `CONTRIBUTING.md`
   - `.github/workflows/ci.yml`
   - `.github/workflows/release.yml`
3. **知识库文档同步**:
   - `docs/project/roadmap.md`（长期演进图谱）
   - `docs/project/backlog.md`（BK-0029~BK-0037 登记）
   - `docs/project/changelog.md`（各阶段交付记录）
   - `docs/reference/api/baidu-pan-sdk.md`（内联路径与接口说明）
   - `docs/index.md` & `docs/llms.txt`

---

## 6. 修订历史 (Revision History)

| 版本 | 日期 | 变更说明 | 维护者 |
| :--- | :--- | :--- | :--- |
| V1.0.0 | 2026-10-28 | 初始创建开源筹备、打包分发与能力补齐实施计划，确立四阶段演进路径 | 主调度智能体 |
