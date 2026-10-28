# bdpan-cli 长期发展路线图 (Product & Architecture Roadmap)

> **文档控制信息**
> - **文档标识**: RDMP-bdpan-cli
> - **当前版本**: V1.0.0
> - **生效日期**: 2026-10-28
> - **文档职责**: 全局演进方向、功能补齐规划、开源战略与包分发体系的设计指南与阶段里程碑（遵循 Diátaxis 架构工程演进象限）。

---

## 1. 愿景与核心定位 (Vision & Principles)

### 1.1 愿景演进
`bdpan-cli` 从最初的个人媒体库规范化整理脚本，全面演进为：
**面向开发者、高级用户与 AI 智能体（Agentic AI）的现代、高性能、可信赖的开源百度网盘终端工具与 SDK**。

### 1.2 核心设计原则
1. **可靠性与资产守恒 (Reliability First)**：
   网盘资产重于泰山。所有破坏性、批量性操作遵循“先只读预演（`--dry-run`）、后对账执行、全链路流水记录（Audit Log）、可逆撤销（Undo）”四道安全底线。
2. **开箱即用与跨平台分发 (Zero-Friction Distribution)**：
   用户无需深究复杂的 Python 依赖与版本冲突。提供 **PyPI (`pip` / `uv tool`)** 标准安装与 **GitHub Releases 跨平台免运行时单文件独立二进制（Linux / macOS / Windows）**。
3. **极速传输与网络容灾 (High Performance Transfer)**：
   融合全量与首片 MD5 云端秒传判定、上传动态机房节点探测优选（`locateupload`）、多线程并发分片下载与断点续传。
4. **AI 原生与自动化友好 (AI-First & Automation Ready)**：
   全量命令支持结构化 `--json` 信封；原生内置 **MCP (Model Context Protocol) Server** 模式，支持各大 AI Coding 客户端（Claude Code、Antigravity、Cursor 等）无缝编排调用。

---

## 2. 开源与全渠道包分发架构 (Open Source & Packaging Architecture)

### 2.1 依赖架构重构：解决 Vendor 阻断点
- **现状瓶颈**：当前通过 `tool.uv.sources.baidu-pan-sdk = { path = "vendor/baidu-pan-sdk", editable = true }` 引入本地修改版 SDK。标准 PyPI（PEP 440 / PEP 517）严禁包携带相对路径依赖，导致无法直接执行 `uv build` 发布至 PyPI。
- **解耦两步走演进路线**：
  1. **短期（v0.2.0 - 快速解耦）**：将 `vendor/baidu-pan-sdk/openapi_client` 完整代码内聚为 `src/bdpan_cli/_vendor/openapi_client` 私有内嵌包，重定向内部引用，彻底移除 `tool.uv.sources`。使源码直接符合标准 Wheel / Sdist 打包规范。
  2. **中期（v0.6.0+ - 轻量原生引擎）**：由于生成的 Swagger/OpenAPI 代码体积大、结构冗余且维护困难，逐步使用轻量级 `PanHttpClient`（基于原生 `httpx` 或精简 `urllib3`）直接对接百度网盘开放平台 REST API，减小安装包体积，支持现代异步 IO。

### 2.2 全渠道分发矩阵 (Distribution Channels)

```
[源代码 (GitHub)] 
       │
       ├──> [CI: uv build] ──> PyPI ──┬──> pip install bdpan-cli
       │                             ├──> uv tool install bdpan-cli
       │                             └──> uvx bdpan-cli (即用即走)
       │
       └──> [CI: PyInstaller 跨平台矩阵] ──> GitHub Releases Assets
                                                  ├──> bdpan-linux-amd64
                                                  ├──> bdpan-linux-arm64
                                                  ├──> bdpan-macos-arm64 (Apple Silicon)
                                                  ├──> bdpan-macos-x86_64 (Intel)
                                                  └──> bdpan-windows-amd64.exe
```

- **Python 包管理**：
  - `pip install bdpan-cli`：传统 Python 环境一键安装；
  - `uv tool install bdpan-cli`：现代隔离环境推荐安装方式；
  - `uvx bdpan <command>`：临时环境无需安装，即时下载并在独立沙箱中执行。
- **独立二进制分发 (Standalone Binaries)**：
  - 基于 GitHub Actions 多操作系统 runner（`ubuntu-latest`, `macos-14`, `macos-13`, `windows-latest`）结合 PyInstaller 打包为单文件可执行文件（无外部 Python 运行时依赖）；
  - 提供快速安装脚本：
    ```bash
    curl -fsSL https://raw.githubusercontent.com/CodingRookie98/bdpan-cli/main/scripts/install.sh | bash
    ```
- **包管理平台进阶扩展 (未来规划)**：
  - macOS Homebrew Tap (`brew install CodingRookie98/tap/bdpan`)；
  - Windows Scoop / Winget 注册支持。

### 2.3 GitHub 开源治理规范
- **开源许可证**: MIT License（宽松友好，鼓励社区生态集成与二次开发）。
- **凭证安全防线**:
  - 核心凭据文件严禁纳入版本库（`.env`, `.baidupan_tokens.json`, `.bdpan_ops/`）；
  - CI 集成 `git-secrets` / `trufflehog` 检测防泄密；
  - 帮助文档一律提供脱敏模板与占位符。
- **开源协作与社区工程**:
  - 完善 `README.md`（中英双语徽章、架构图、功能对比、快速开始）；
  - 完备的 `CONTRIBUTING.md`（本地搭建、开发工作流、TDD 与测试门禁规范）；
  - GitHub Actions 自动化门禁（PR 自动化跨 Python 3.12/3.13 单元测试、文档链接健康度检查）。

---

## 3. 四阶段能力演进图谱 (Phased Evolution)

### 阶段一：开源就绪与打包分发基建 (Phase 1: Foundations & Packaging)
**目标**：扫清打包阻断，完成标准包构建与自动化发布流水线，正式开源。
- [x] **Vendor SDK 内联化与相对路径解耦**：移除 `tool.uv.sources`，将依赖内聚至 `src/bdpan_cli/_vendor/`，支持标准 `uv build`。
- [x] **开源工程标准建立**：补充 `LICENSE` (MIT)、`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、Issue/PR Templates。
- [x] **GitHub Actions 自动化流水线**：
  - `ci.yml`：Push/PR 多版本测试与文档检查；
  - `pypi-publish.yml`：基于 GitHub Trusted Publishing 自动化发版至 PyPI；
  - `release-binaries.yml`：PyInstaller 跨平台编译打包与 Assets 发布。
- [x] **配置与凭据解耦完善**：支持全局配置文件路径 `~/.config/bdpan/` 或环境变量自定义指定，防止工作区混淆。

### 阶段二：传输核心能力补齐与极速优化 (Phase 2: Core Transfer & Performance)
**目标**：补齐文件下载与秒传上传，实现全能力闭环与极致传输体验（对标 `boxplayer` 核心优势）。
- [x] **大文件下载与断点续传 (`bdpan download`)**：
  - 调用 `filemetas&dlink=1` 获取真实下载直链；
  - 注入 `User-Agent: pan.baidu.com` 请求头规避防盗链 403 限速；
  - 支持多线程并发分块下载、中断自动恢复（`.download_state` 状态记忆）。
- [x] **直链与导出命令 (`bdpan dlink`)**：
  - 快速输出单文件/批量文件的直链 URL、有效时长；
  - 支持输出配套 `aria2c` / `curl` / `wget` 下载命令脚本，便于外部离线下载工具接入。
- [x] **极速秒传与动态机房接入 (`bdpan upload`)**：
  - 在大文件上传的 `precreate` 阶段，计算首片 256KB MD5 与全量 MD5 进行云端碰撞检测；命中时直接触发秒传完成，0 网络流量消耗；
  - 上传分片前调用 `locateupload` 接口动态获取距离当前客户端物理延时最低、带宽最优的机房服务器 host，显著降低传输抖动与超时重试。

### 阶段三：安全运维与多账号体系 (Phase 3: Safety Ops & Multi-Account)
**目标**：保障生产级运维安全，实现操作可逆与多身份无缝切换。
- [x] **操作流水审计与逆向撤销 (`bdpan ops` & `bdpan undo`)**：
  - 所有批量重命名、批量移动、清理与去重操作均落盘结构化审计日志至 `~/.config/bdpan/ops/<op_id>.json`；
  - 新增 `bdpan ops list` 和 `bdpan ops show <op_id>` 查阅历史操作详情；
  - 新增 `bdpan undo <op_id>` 命令：反向解析操作记录，生成逆向变更 Plan，支持 `--dry-run` 预览回滚与一键安全复原，防止误操作。
- [x] **多账号配置与动态切换 (`bdpan auth`)**：
  - 支持管理多组网盘凭证与别名（如 `personal`、`work`、`backup`）；
  - 新增 `bdpan auth list`、`bdpan auth add <alias>`、`bdpan auth switch <alias>`；
  - 全局支持 `--account <alias>` 参数，单次命令定向指定操作账号。

### 阶段四：媒体可观测性与 AI 原生集成 (Phase 4: Media Insights & AI/MCP)
**目标**：深化媒体专业管理能力，全面拥抱 Agentic AI 生态。
- [ ] **媒体深度元数据解析 (`bdpan info`)**：
  - 对网盘视频文件获取准确的编码格式（H.264/HEVC/AV1）、分辨率、音轨数、时长与码率；
  - 辅助刮削器更智能地识别画质等级与音效标准。
- [ ] **目录聚合与容量统计 (`bdpan stats`)**：
  - 轻量化快速统计指定网盘目录的文件总量、总大小、媒体格式占比与拓扑深度。
- [ ] **全局结构化输出与机器信封 (`--json`)**：
  - 所有 CLI 子命令均支持 `--json` 输出模式，输出标准化的 `{ "code": 0, "data": ..., "msg": "ok" }` 信封，便于管道与脚本解析。
- [ ] **原生 MCP (Model Context Protocol) Server 模式 (`bdpan mcp`)**：
  - 封装 FastMCP 服务端，自省导出网盘操作的 Tool Schemas；
  - 允许大语言模型助手通过标准 MCP 协议直接调用网盘列举、搜索、下载、移动与整理等能力。

---

## 4. 里程碑与版本规划 (Milestones & Release Plan)

| 版本号 | 核心交付内容 | 关键标志 | 预期发布渠道 |
| :--- | :--- | :--- | :--- |
| **v0.2.0** | 打包解耦与开源准备 | Vendor 内联、开源规范、GitHub Actions 初始流水线 | GitHub / PyPI (`bdpan-cli`) |
| **v0.3.0** | 核心传输：下载与秒传 | `bdpan download`、`dlink` 提取、`upload` 秒传与 `locateupload` | PyPI / GitHub Releases (二进制) |
| **v0.4.0** | 安全运维：操作流水与撤销 | `.bdpan_ops/` 流水落盘、`bdpan ops`、`bdpan undo` 可逆撤销 | PyPI / GitHub Releases / `uv tool` |
| **v0.5.0** | 身份隔离：多账号体系 | 多 Token 别名管理、`bdpan auth switch`、`--account` 参数 | PyPI / GitHub Releases |
| **v0.6.0** | 原生轻量 HTTP 引擎演进 | 剥离 OpenAPI 生成代码，引入精简 `PanHttpClient`，包体瘦身 | PyPI / 全平台二进制 |
| **v1.0.0** | AI 原生与企业级稳定版 | 原生 `bdpan mcp`、媒体 `info`/`stats`、全局 `--json`、稳定正式版 | PyPI / GitHub Releases / Homebrew |

---

## 5. 修订历史 (Revision History)

| 版本 | 日期 | 变更说明 | 维护者 |
| :--- | :--- | :--- | :--- |
| V1.0.0 | 2026-10-28 | 初始创建长期演进路线图：确立开源发布、包分发架构、Vendor 解耦与四阶段能力图谱 | 主调度智能体 |
