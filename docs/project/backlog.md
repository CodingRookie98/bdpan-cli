# 待办与后续方向 (Backlog)

> **控制信息**
> - **文档版本**: V1.7.0
> - **文档标识**: BKLG-bdpan-cli
> - **生效日期**: 2026-10-28
> - **条目规范**: [backlog-specification.md](../../.agents/skills/doc-governance/references/backlog-specification.md)
> - **演进计划**: [roadmap.md](./roadmap.md) | [2026-10-28 实施计划](./plans/2026-10-28-roadmap-and-open-source-packaging.md)

## 进行中

（暂无进行中任务）

## 计划中 (路线图演进任务)

### 阶段一：开源合规与全渠道打包分发基建 (Phase 1)
- [ ] BK-0029 Vendor SDK 内联化与相对路径解耦（将 `vendor/baidu-pan-sdk/openapi_client` 迁移至 `src/bdpan_cli/_vendor/openapi_client`，移除 `pyproject.toml` 中的 `tool.uv.sources` 相对依赖，实现标准纯净包构建）
- [ ] BK-0030 GitHub 开源合规与工程化建设（新增 `LICENSE` MIT、完善 `CONTRIBUTING.md`、更新 `README.md` 双语徽章与全渠道安装说明、强化敏感凭据 `.gitignore` 防泄密机制）
- [ ] BK-0031 GitHub Actions 自动化 CI/CD 与跨平台单文件二进制发布（配置多 Python 版本矩阵测试 `ci.yml`、PyPI Trusted Publishing 自动化发版、PyInstaller 编译 Linux/macOS/Windows 单文件免运行环境二进制可执行档）

### 阶段二：传输核心能力补齐与极速优化 (Phase 2)
- [ ] BK-0032 大文件下载与断点续传引擎（新增 `bdpan download` 与 `bdpan dlink` 命令；调用 `filemetas&dlink=1`，注入 `User-Agent: pan.baidu.com` 防 403 限速，支持多线程分块下载与 `.download_state` 断点续传，支持导出 aria2c/curl 命令）
- [ ] BK-0033 极速秒传机制与动态最优机房接入（大文件上传 `precreate` 阶段计算首片 256KB MD5 与全量 MD5 进行云端碰撞，命中直接秒传 0 流量完成；上传前调用 `locateupload` 动态获取延时最低最优机房 host，提升网络稳定性）

### 阶段三：安全运维体系与多账号隔离 (Phase 3)
- [ ] BK-0034 操作流水审计与逆向撤销体系（本地落盘 `.bdpan_ops/<op_id>.json` 记录批量更名/移动/去重等操作映射；新增 `bdpan ops list/show` 以及 `bdpan undo <op_id>` 逆向撤销命令，支持 `--dry-run` 预览与一键安全复原）
- [ ] BK-0035 多账号认证管理与动态切换（升级 TokenManager 支持多账号别名存储；新增 `bdpan auth list/add/switch` 子命令，CLI 根命令新增全局 `--account <alias>` 参数支持多网盘账号无缝切换）

### 阶段四：媒体可观测性与 AI 原生集成 (Phase 4)
- [ ] BK-0036 全局结构化输出与媒体深度元数据解析（所有 CLI 子命令支持 `--json` 标准信封输出；新增 `bdpan info <file>` 探测视频编码/分辨率/时长/码率，新增 `bdpan stats <dir>` 目录聚合容量统计）
- [ ] BK-0037 原生 MCP (Model Context Protocol) Server 集成（实现 `bdpan mcp` 子命令，自省暴露 CLI 能力为标准 MCP Tool Schemas，支持 Claude Code、Antigravity、Cursor 等 AI 编程助手直接编排操作网盘）

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
| V1.7.0 | 2026-10-28 | 演进路线图与开源打包规划：登记 BK-0029~BK-0037，确立四阶段能力演进、全渠道包分发与 Vendor 解耦规划 |
| V1.6.0 | 2026-10-28 | 刮削器健壮性修复：关闭 BK-0028（解决未带空格 4K/2K 等标签粘连片名缺陷，translations 优先选取 CN 简体中文译名），测试 126→128 全绿 |
| V1.5.0 | 2026-10-27 | 质量加固与自动化整理增强批次：关闭 BK-0024~BK-0027（刮削器 Welsh 过滤与序号剥除、ls 路径不存在报错与单文件展示、foldering 穿透扫描与字幕识别、dedup 冲突副本治理与 batch_delete），测试 104→126，实测全链路通过 |
| V1.4.0 | 2026-10-07 | CLI 基础功能收尾批次：关闭 BK-0018~BK-0022（多源批量/递归树+索引/搜索/分片上传+续传/容量账户），测试 52→104，全项真网盘 L2 实测 |
| V1.3.0 | 2026-10-07 | BK-0017 第三阶段 `meta` 子系统划为待定（Kodi/Emby/Jellyfin 可依目录名 IMDb/TMDB ID 精准刮削，待用户/社区需求再立项），开发重心转向 CLI 基础功能收尾 |
