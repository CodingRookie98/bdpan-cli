# 待办与后续方向 (Backlog)

> **控制信息**
> - **文档版本**: V1.11.0
> - **文档标识**: BKLG-bdpan-cli
> - **生效日期**: 2026-10-28
> - **条目规范**: [backlog-specification.md](../../.agents/skills/doc-governance/references/backlog-specification.md)
> - **演进计划**: [roadmap.md](./roadmap.md) | [2026-10-28 实施计划](./plans/2026-10-28-roadmap-and-open-source-packaging.md)

## 进行中

（暂无进行中任务）

## 计划中 (路线图演进任务)

### 文档与规范专项
- [ ] BK-0023 文档治理体系落地：tutorials / how-to / explanation 象限按需填充

## 待定（暂缓，待需求触发）

> 方案 A 目录名规范化刮削已全量落地（BK-0007/BK-0010），电影目录名末尾携带 IMDb/TMDB ID，Kodi/Emby/Jellyfin 等媒体管理器可直接依据目录名完成精准刮削，CLI 暂不自建完整元数据子系统；待用户或社区提出明确需求后重新立项推进。

- [ ] BK-0017 `[Trigger:用户/社区明确需求]` 第三阶段：电影元数据与封面海报全量自动化生成与上传 (`meta` 子系统)
  - [ ] `bdpan meta nfo <dir>`：依据方案 A 目录名末尾的 IMDb/TMDB ID，精准查询 TMDB 电影详情并生成符合 Kodi/Emby/Jellyfin 格式的 `movie.nfo`（支持评分、演职员、分级、标签、中文简介等）
  - [ ] `bdpan meta poster <dir>`：下载 TMDB 最高清竖版官方海报，流式调用百度网盘上传接口写入各电影根目录的 `poster.jpg`
  - [ ] 支持断点续传、已存在跳过（幂等性）与 `--dry-run` 预览模式
  - [ ] 对 `/影视/电影/watched`（266部）与 `/影视/电影/unwatched`（36部）共 302 部电影全量批处理

## 已关闭

- [x] BK-0040 顶层帮助打印开源仓库与作者信息、确立远端 Issue 反馈指引与代码库正式开源上云（创建并推送远端公共仓库 `origin` 至 `https://github.com/CodingRookie98/bdpan-cli`；`cli.py` 顶层 `--help` 头部描述与底部 `epilog` 输出开源地址与作者信息；`skills/bdpan-cli/SKILL.md` 与 `AGENTS.md` 增加缺陷主动提醒远端提 Issue 规约；单测 175 项全绿，2026-10-29）
- [x] BK-0039 CLI 全局 --help 体验与示例完善及 Skill 安装审批治理（`cli.py` 为全量 32 个一级与二级子命令全面配备规范的 `description` 功能定位概述、底部 `epilog` 实操高频调用样例与显式默认值标注；`skills/bdpan-cli/SKILL.md` 增加安装指南，并确立系统缺失 CLI 时必须向用户明确申请安装审批方可安装的强制军规；单测 174→175 全绿，2026-10-29）
- [x] BK-0038 电影刮削目录命名自定义模板支持（`scraper.py` 新增 `MovieMetadata.format_name` 与 SafeDict 容错字典映射，支持 `{title}`, `{original_title}`, `{year}`, `{id}`, `{imdb_id}`, `{tmdb_id}`, `{edition}` 占位符自由组合；`preview_scrape.py` 与 `foldering.py` 新增 `name_format` 参数；`cli.py` 在 `scrape preview` 与 `scrape foldering` 增加 `--format` 选项，未指定时默认保持方案 A 行为 100% 向后兼容；单元测试 170→174 全绿，2026-10-29）
- [x] BK-0037 原生 MCP (Model Context Protocol) Server 集成（新增 `mcp_server.py` 与 `bdpan mcp` 子命令，基于标准 stdio 纯净实现 JSON-RPC 2.0 协议生命周期 initialize/ping/tools/list/tools/call，自省暴露网盘 14 项核心文件管理与可观测性 Tool Schemas，支持 Claude Code、Antigravity、Cursor 直接调用；单测全绿，2026-10-28）
- [x] BK-0036 全局结构化输出与媒体深度元数据解析（所有核心查询命令支持 `--json` 标准化信封输出；新增 `MediaInfoClient` 模块与 `bdpan info`、`bdpan stats` 命令，支持视频精准分辨率 4K/1080P、时长、HEVC/H.264 编码、音轨探测与目录容量分类聚合统计；单测全绿，2026-10-28）
- [x] BK-0035 多账号认证管理与动态切换（升级 TokenManager 支持多账号别名存储与自动平滑迁移旧单账号缓存；新增 `bdpan auth list/switch/login` 子命令，CLI 根命令新增全局 `--account <alias>` 参数支持多网盘账号隔离与即时切换；单测验证通过，2026-10-28）
- [x] BK-0034 操作流水审计与逆向撤销体系（本地落盘 `.bdpan_ops/<op_id>.json` 结构化记录批量更名/移动操作映射清单；新增 `bdpan ops list/show` 以及 `bdpan undo <op_id>` 逆向撤销命令，支持 `--dry-run` 预览与一键安全复原；单测覆盖正向记录与逆向撤销，2026-10-28）
- [x] BK-0033 极速秒传机制与动态最优机房接入（大文件上传 `precreate` 命中 `return_type == 2` 时跳过分片上传直接创建，0 流量瞬间完成；新增 `locate_upload_host` 动态获取最优上传服务器 host，单测验证通过，2026-10-28）
- [x] BK-0032 大文件下载与断点续传引擎（新增 `Downloader` 模块与 `bdpan download`、`bdpan dlink` 子命令；调用 `filemetas&dlink=1` 获取真实下载直链，注入 `User-Agent: pan.baidu.com` 防限速，支持分块断点续传与导出 aria2c/curl 命令，单测全绿，2026-10-28）
- [x] BK-0031 GitHub Actions 自动化 CI/CD 与跨平台单文件二进制发布（配置多 Python 版本矩阵测试 `ci.yml`、PyPI Trusted Publishing 自动化发版、PyInstaller 编译 Linux/macOS/Windows 单文件免运行环境二进制可执行档，实测本地单文件二进制 Exit Code 0，2026-10-28）
- [x] BK-0030 GitHub 开源合规与工程化建设（新增 `LICENSE` MIT、完善 `CONTRIBUTING.md`、更新 `README.md` 双语徽章与全渠道安装说明、强化敏感凭据 `.gitignore` 防泄密机制，2026-10-28）
- [x] BK-0029 Vendor SDK 内联化与相对路径解耦（将 `vendor/baidu-pan-sdk/openapi_client` 迁移至 `src/bdpan_cli/_vendor/openapi_client`，移除 `pyproject.toml` 中的 `tool.uv.sources` 相对依赖，解除 PyPI 打包封锁；在独立临时干净 venv 中 pip 安装验证通过；全量 128 项单测全绿，2026-10-28）
- [x] BK-0028 电影刮削器中文提取粘连修复与简体中文译名优先级保障（`scraper.py` 修复未带空格的 `4K`/`2K` 等画质标签附着在汉字后被连带提取为中文片名的缺陷，TMDB translations 解析时优先匹配 `iso_3166_1 == "CN"` 简体中文；单测 +2，126→128 全绿，2026-10-28）
- [x] BK-0027 网盘冲突副本与重复文件治理命令（新增 `dedup` 命令与 `src/bdpan_cli/dedup.py`；识别 `(1)`/`(2)` 冲突后缀、`--staging-dir` 暂存隔离与 `--delete` 回收站清理，`--dry-run` 预演与空目录检测；`FileManager.batch_delete` 50 项分批保护；测试 110→126，2026-10-27）➔ [9753f3d]
- [x] BK-0026 散落媒体归集穿透与字幕识别补全（`foldering.py` 扩展名扩充字幕 `.srt`/`.ass`/`.sub`/`.vtt`，穿透扫描非方案 A 子目录中的媒体与字幕并原子归集；测试 109→110，2026-10-27）➔ [07fc69f]
- [x] BK-0025 目录列表不存在路径与单文件可观测性增强（`cli.py` `cmd_ls` 遇空列表探测父目录，确认不存在输出 `❌ 路径不存在` 并退出码 1；单文件路径直接展示文件大小，测试 106→109，2026-10-27）➔ [4a75b68]
- [x] BK-0024 电影刮削器健壮性加固（`scraper.py` 修复 TMDB 英文译名 Welsh/cy 小语种穿透 Bug，严格校验 `iso_639_1 == "en"`；剥除片名开头 `01 ` 等序号与标点噪声；测试 104→106，2026-10-27）➔ [f43de2f]
- [x] BK-0021 大文件分片上传与断点续传（`Uploader` 三阶段 precreate/superfile2/create，本地状态文件续传真中断 E2E 实测：80MB 20 片传至 5 片中断后仅补 15 片原 uploadid 原路径成功；服务端不跨 uploadid 记忆分片为实测结论，2026-10-07）➔ [a96268b]
- [x] BK-0022 网盘容量与用户信息查询（`AccountClient` quota/whoami 两命令，SDK 模型对象归一化，真网盘 L2 只读实测，2026-10-07）➔ [e9374e0]
- [x] BK-0020 文件搜索 CLI（`FileManager.search` + `search` 命令，全盘/限目录/递归开关/翻页，实测命中方案 A 规范目录；实测服务端忽略 num 参数，2026-10-07）➔ [f06fff3]
- [x] BK-0019 递归遍历网盘文件树并落地本地索引（`FileManager.walk` DFS 先序 + `tree` 命令 `--index` 全字段保真 JSON；`xpanfilelistall` 实测 errno=20020 应用权限受限全路径不可用，引擎改用 xpanfilelist 客户端侧递归，实测 2290 条零失败，2026-10-07）➔ [12f7cd1]
- [x] BK-0018 文件操作命令多源批量参数（`cp`/`mv` 源参数 nargs='+'，`_require_dest_dir` 目录语义校验，多源走既有 batch 基建；真网盘沙箱批量 mv/cp 实测 + 零残留，2026-10-07）➔ [9dbd779]
- [x] BK-0016 (P4 审查建议) `FileManager.copy` 错误文案去掉"批量复制批次 1"字样（copy 改走共享 `_copy_request` 单项语境文案通道，真批量场景既有文案逐字保留，2026-09-30）
- [x] BK-0015 (P4 审查建议·立项) filemanager 四原语（copy/move/rename/delete）逐项 `info[].errno` 校验统一加固（新增 `_validate_filemanager_result` 统一助手；真网盘沙箱故障注入取证：部分失败信封顶层 `errno=12` + `info[].errno=-9`，混合批有效项实际生效，delete 缺源幂等返回 0，2026-09-30）
- [x] BK-0014 (P4 审查建议) `rm` 交互确认补 EOFError/KeyboardInterrupt 守卫（非交互 stdin / Ctrl-C 视作取消，退出 0 不删除，2026-09-30）
- [x] BK-0013 (P4 审查建议) `_resolve_dest` 探测失败 fallback 分支补 `logger.warning`（2026-09-30）
- [x] BK-0012 文件操作命令补齐：新增 `cp`/`rm`/`rename`，修复 `mv` 移动改名语义（`FileManager.copy`/`batch_copy`，真网盘沙箱全链路实测通过，2026-09-30）
- [x] BK-0011 项目全面重新定位与品牌重命名：重命名为 `bdpan-cli`，主命令 `bdpan`（完成代码包迁移、pyproject.toml、CLI 别名与全量测试，2026-09-29）
- [x] BK-0010 媒体库终态拓扑规整（`unscraped` 电影并入 `watched`，`pending_triage` 更名为 `torrents`，全库 302 部电影 100% 达标，2026-09-29）
- [x] BK-0009 工程化统一 CLI 工具构建与 `scrape foldering` 落地（实现统一子命令体系，完成 `/影视/电影/unscraped` 17个散落文件建目录与规整，2026-09-29）
- [x] BK-0008 特殊条目解耦与分类（`Scario(1-2)` 拆分为边境杀手 1 与 2，`Seed.Bank` 归集至 `pending_triage`，2026-09-29）
- [x] BK-0007 电影目录名方案 A 规范化刮削与批量更名（`unwatched` 36部 + `watched` 251部，全量 287 部 100% 达标，2026-09-29）
- [x] BK-0006 电影目录结构规整第一步（`unwatched` 重命名、`watched` 归档、`pending_triage` 杂项归集，2026-09-29）
- [x] BK-0005 文件管理核心能力封装（`FileManager`: mkdir / rename / batch_move / list_dir，2026-09-29）
- [x] BK-0004 官方 Python SDK 获取与集成（vendor 包 `baidu-pan-sdk`，2026-09-29）
- [x] BK-0003 设备码授权与 token 缓存（`auth.py` TokenManager，2026-09-29）
- [x] BK-0002 目录列表 CLI（2026-09-29）
- [x] BK-0001 SDK 接口参考文档基线（2026-09-29）

## 修订历史

| 版本 | 日期 | 变更摘要 |
|:---|:---|:---|
| V2.3.0 | 2026-10-29 | 开源上云与元信息呈现：关闭 BK-0040（代码库推送至 GitHub 公开仓库，顶层 --help 展示仓库与作者信息，SKILL.md 补充远端提 Issue 反馈指引），单测 175 项全绿 |
| V2.2.0 | 2026-10-29 | CLI 体验与审批门禁交付：关闭 BK-0039（`cli.py` 32 个命令补齐 description 概述与底部实战示例 epilog，SKILL.md 补充安装说明与未安装强制审批军规），单测 174→175 全绿 |
| V2.1.0 | 2026-10-29 | 电影刮削自定义模板交付：关闭 BK-0038（`format_name` 字段自由组合与容错字典，`scrape preview` / `foldering` 新增 `--format` 参数，默认方案 A 向后兼容），单测 170→174 全绿 |
| V2.0.0 | 2026-10-28 | Phase 3/4 安全体系与 AI 原生交付：关闭 BK-0034~BK-0037（操作流水审计/逆向撤销、多账号隔离、媒体深度元数据探测/聚合统计、原生 stdio MCP Server），单测 140→170 全绿 |
| V1.9.0 | 2026-10-28 | Phase 2 传输核心交付：关闭 BK-0032（Downloader 模块、`download` 断点续传与 `dlink` 直链与防限速）与 BK-0033（极速秒传机制与 `locate_upload_host` 动态机房接入），测试 128→140 全绿 |
