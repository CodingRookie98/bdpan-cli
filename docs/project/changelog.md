# 变更日志 (Changelog)

> 记录每次交付的功能与文档演进。格式：日期 + 版本 + 变更摘要。

## 2026-10-29

- **feat(cli)**: CLI 全局 --help 体验与实操示例完善及 Skill 安装审批治理（BK-0039）。
  - **BK-0039 (--help 丰富度与实战样例)**: `cli.py` 为全量 32 个一级与二级子命令全面增补 `description` 功能定位概述与底部的 `epilog` 实操高频调用样例（涵盖单源改名/多源复制、大文件秒传与断点续传、直链提取与多线程导出、影视刮削预演应用与自定义模板组合、操作审计回滚、多账号管理隔离与 MCP stdio 启动等）；统一配置 `RawDescriptionHelpFormatter` 保留排版结构；完善参数默认值标注；
  - **智能体 Skill 治理与审批红线**: 更新 `skills/bdpan-cli/SKILL.md`，增加 5 种安装指引，并确立在环境中缺失 `bdpan` CLI 时智能体必须暂停并明确向用户获得安装审批的严格军规；
  - **单元测试扩充**: 新增 `test_cli_subparsers_rich_help`，抽样与全量回归测试套件增至 175 项全绿通过（`175 passed in 5.79s`）。
- **feat(scraper)**: 电影刮削目录命名自定义模板支持（BK-0038）。
  - **BK-0038 (命名模板自由组合与容错)**: `scraper.py` 新增 `MovieMetadata.format_name(template)` 方法，引入 `SafeDict` 容错字典，支持 `{title}`, `{original_title}`, `{year}`, `{id}`, `{imdb_id}`, `{tmdb_id}`, `{edition}` 等占位符自由组合；`formatted_name` 保持无参默认方案 A 命名；
  - **CLI 参数支持**: `preview_scrape.py` 与 `foldering.py` 分别扩充 `name_format` 传参；`cli.py` 在 `scrape preview` 与 `scrape foldering` 注册 `--format` 参数，支持 Plex 官方模板、点号紧凑模板与自定义中英文格式；未指定时默认保持方案 A 规范不变，100% 向后兼容；
  - 全量测试套件从 170 项扩充至 174 项全绿通过（`174 passed in 7.06s`）。
- **docs(skill)**: 全面同步升级 `skills/bdpan-cli/SKILL.md` 智能体专属技能手册。
  - 架构描述更正为标准内聚包（`src/bdpan_cli/_vendor/openapi_client`）；
  - 全量补充 Phase 1~4 交付的所有新命令速查（`download`, `dlink`, `ops`, `undo`, `auth`, `info`, `stats`, `mcp` 以及全局 `--account` 和 `--json`）；
  - 扩充 6 类高频工作流范例（直链提取与多线程脚本导出、操作流水审计与逆向回滚还原、多账号隔离操作、视频深度元数据探测、AI 助手接入原生 MCP Server 等）。
- **chore(python)**: 拓展 Python 3.14 兼容性认证。
  - `pyproject.toml` 新增 `Programming Language :: Python :: 3.14` 分类器；
  - `.github/workflows/ci.yml` 自动化测试矩阵扩充覆盖 Python 3.12、3.13、3.14；
  - 维持 `requires-python = ">=3.12"` 工业界向下兼容基线，保障存量系统与最新环境兼具 100% 可用性。

## 2026-10-28

- **feat(insights-ai)**: Phase 4 媒体可观测性与 AI 原生集成交付（BK-0036~BK-0037）。
  - **BK-0036 (全局结构化输出与媒体深度元数据解析)**: 引入 `MediaInfoClient`（`media_info.py`）与 `bdpan info`、`bdpan stats` 终端命令；`info` 支持通过网盘 `xpanmultimediafilemetas` 接口探测视频分辨率标称（如 `3840x2160 (4K UHD)` / `1080P FHD`）、时长 `HH:MM:SS`、HEVC/H.264 视频编码与音轨数；`stats` 递归聚合统计目录总容量、总文件数及媒体格式占比；所有核心查询命令支持 `--json` 输出标准化结构化信封，方便第三方脚本化消费；
  - **BK-0037 (原生 MCP Server 模式集成)**: 新增 `BdpanMcpServer`（`mcp_server.py`）与 `bdpan mcp` 终端命令；基于轻量零重量外部依赖的纯净 Python 协议栈原生实现 Model Context Protocol (MCP) 与 JSON-RPC 2.0 完整生命周期（`initialize`、`ping`、`tools/list`、`tools/call`）；自省暴露网盘 14 项核心文件操作与可观测性 Tool Schemas，支持 Claude Code、Antigravity、Cursor 等 AI 编程助手直接配置调用；
  - 全量测试套件从 155 项扩充至 170 项全绿通过（`170 passed in 6.00s`）。
- **feat(safety)**: Phase 3 安全运维体系与多账号隔离交付（BK-0034~BK-0035）。
  - **BK-0034 (操作流水审计与逆向撤销体系)**: 新增 `ops.py`（`OperationLogger` 与 `UndoEngine`）以及 `bdpan ops`、`bdpan undo` 终端命令；所有批量更名、批量移动、归集等关键操作原子落盘结构化审计日志至 `.bdpan_ops/<op_id>.json`（包含时间、命令、账号、操作前后映射路径）；`ops list` / `ops show` 查阅历史流水；`undo <op_id>` 逆向解析操作对并基于 `FileManager.batch_move` 执行逆向回滚，支持 `--dry-run` 预览回滚与一键安全复原，状态自动标记 `undone` 防止重复执行；
  - **BK-0035 (多账号认证管理与动态切换)**: 重构升级 `TokenManager`（`auth.py`），支持以账号别名存储多套凭证，并自动平滑升级旧单账号缓存文件；新增 `bdpan auth list`、`bdpan auth switch <alias>`、`bdpan auth login [--account <alias>]` 子命令；CLI 根命令新增全局 `--account <alias>` 参数，支持单次命令动态指定网盘租户；
  - 全量测试套件从 140 项扩充至 155 项全绿通过（`155 passed in 5.84s`）。
- **feat(transfer)**: Phase 2 传输核心能力补齐与极速优化交付（BK-0032~BK-0033）。
  - **BK-0032 (大文件下载与直链提取)**: 新增 `Downloader` 模块（`downloader.py`）与 `bdpan download`、`bdpan dlink` 终端命令；调用 `MultimediafileApi.xpanmultimediafilemetas(dlink=1)` 获取真实直链，全局强制注入 `User-Agent: pan.baidu.com` 请求头防 403 限速；支持大文件分块断点续传（基于 `.tmp` 临时文件与 HTTP Range 协议）与同名跳过/覆盖保护；`dlink` 命令支持 `--aria2` 与 `--curl` 直接导出多线程高速下载脚本；
  - **BK-0033 (极速秒传与动态机房接入)**: 升级 `Uploader`（`uploader.py`），在 `precreate` 预上传阶段若服务端返回 `return_type == 2`（特征命中云端秒传）则直接跳过分块数据传输直接调用 `_create`，实现 0 流量秒传；新增 `locate_upload_host` 原语，上传前动态向百度请求延时最低的最优机房 host 列表，提升跨网络运营商传输稳定性；
  - 全量测试套件从 128 项扩充至 140 项全绿通过（`140 passed in 7.16s`）。
- **feat(packaging)**: Phase 1 开源打包与全渠道分发基建交付（BK-0029~BK-0031）。
  - **BK-0029 (Vendor 解耦与内联化)**: 将 `vendor/baidu-pan-sdk/openapi_client` 内聚至 `src/bdpan_cli/_vendor/openapi_client`，调整所有模块命名空间引用；移除 `pyproject.toml` 中的 `[tool.uv.sources]` 本地相对路径依赖，添加标准 PyPI 元数据与分类器，使项目直接支持标准 Wheel 与 Sdist 构建（`uv build` 生成标准产物），在全新隔离虚拟环境中 pip 安装验证通过；
  - **BK-0030 (开源工程与合规规范)**: 新增 `LICENSE` (MIT License)；新增 `CONTRIBUTING.md` 贡献开发手册（涵盖本地搭建、测试门禁与提交规范）；更新根目录 `README.md`，添加开源徽章与全渠道安装说明（`uv tool` / `uvx` / `pip` / Releases 单文件二进制）；加固 `.gitignore` 凭证与构建文件防泄密保护；
  - **BK-0031 (CI/CD 自动化与跨平台二进制流水线)**: 引入 PyInstaller 单文件跨平台构建设施，本地与多架构实测成功生成独立运行的单文件二进制执行档 `dist/bdpan`；编写 `.github/workflows/ci.yml`（PR/Push 跨 Python 3.12/3.13 自动化测试与文档门禁）与 `.github/workflows/release.yml`（Tag 触发 PyPI Trusted Publishing 与多平台二进制 Releases 自动打包上传）；
  - 全量 128 项单元测试保持全绿通过（`128 passed in 6.8s`）。
- **fix(scraper)**: 电影刮削器中文片名粘连修复与简体中文译名优先级保障（BK-0028）。
  - `scraper.py` 修复中文提取时未带空格的 `4K`/`2K` 等画质标签被误连入中文候选词导致片名截断污染的缺陷（如《竖锯4K》被误提取为《竖锯4》）；
  - `_extract_detail_meta` 优先选取 `iso_3166_1 == "CN"` 的简体中文译名，避免繁体译名（TW/HK）由于遍历次序领先导致覆盖；
  - 单元测试 +2（126→128 passed）。
- **ops(media)**: 完成网盘 `/videos/movies/unscraped` 目录下《电锯惊魂》全系列 1~9 部（含 4K REMUX 与字幕）方案 A 规范化刮削与迁移至 `/videos/movies/unwatched`；清理外层空合集目录，网盘资产与文件数量严格守恒，合规率 100%。
- **docs**: 根目录新增项目级规约 `AGENTS.md`，确立在 CLI 工具使用过程中发现缺陷、Bug、功能需求时向用户汇报并提供选项的 3 步闭环确认机制。

## 2026-10-27

- **feat(cli)**: 网盘冲突副本与重复文件治理命令（BK-0027）。新增 `dedup` 子命令（`dedup.py`），支持自动识别 `(1)`/`(2)` 冲突后缀、无主编号冗余副本及空目录；提供 `--dry-run` 预演、`--staging-dir` 暂存隔离（防直接误删）与 `--delete` 回收站清理；`FileManager` 新增 `batch_delete` 原语（50 项/批切分 + 逐项 errno 校验）；单元测试 +16，全量测试 110→126。
- **feat(scrape)**: 散落媒体归集穿透与字幕识别补全（BK-0026）。`foldering.py` `ALLOWED_EXTENSIONS` 扩展支持常见外挂字幕（`.srt`/`.ass`/`.sub`/`.vtt`）；`plan_foldering` 增加对非方案 A 子目录的内部穿透扫描与归集；单元测试 109→110。
- **fix(cli)**: 目录列表不存在路径与单文件可观测性增强（BK-0025）。`cli.py` `cmd_ls` 在 `list_dir` 返回空列表时主动探测父目录，确认不存在时输出 `❌ 路径不存在: <path>` 并返回退出码 1；当目标为单文件时直接格式化输出文件大小与详情；单元测试 106→109。
- **fix(scraper)**: 电影刮削器健壮性加固（BK-0024）。`scraper.py` 修复 TMDB translations 遇到英国发售区包含 Welsh (cy) 译名时导致英文原名被威尔士语覆盖的穿透缺陷（严格校验 `iso_639_1 == "en"`）；片名清洗剥除开头的 `01 ` 等序号噪声；单元测试 104→106。
- **feat(skills)**: 新增 `skills/bdpan-cli/SKILL.md` 智能体专属技能手册，建立环境执行规范、命令速查表、方案 A 刮削标准与常见工作流指引。
- **ops(media)**: 完成网盘 `/影视/电影` 路径更名（`/videos/movies`，307 部电影目录完全守恒）；完成 `/videos/movies/unscraped` 下《玩具总动员》全系列 7 部作品（含 4K REMUX/mUHD/1080P 多版本与外挂字幕）规范化归集至 `unwatched`，17 个冲突/空目录安全隔离至 `pending_delete`。

## 2026-10-07

- **feat(cli)**: 大文件分片上传与断点续传（BK-0021）。新增 `Uploader`（`uploader.py`）实现官方三阶段流程：预上传（`autoinit=1`、逐片 4MB 流式 MD5）→ 分片上传（`type=tmpfile`、瞬时失败重试 3 次）→ 创建文件（`block_list`/`uploadid`/`rtype` 与预上传严格一致）；`rtype` 默认 1 冲突自动改名、`--overwrite` 为 3 覆盖。断点续传采用本地状态文件（`.bdpan_uploads.json`，git-ignored）记录 uploadid 与已传分片——真网盘实测服务端不按路径跨 uploadid 记忆分片，恢复时凭原 uploadid 仅补缺失片，uploadid 失效自动回退全新上传。SDK 适配实证：`superfile2` file 参数要求带 `.name` 的 IOBase、分片成功响应无 `errno` 字段、precreate 对本应用在非 `/apps` 路径可用。真网盘 L2：9MB 全新上传大小精确一致；80MB/20 片真中断（kill 进程树）后重跑仅补传 15 片原路径成功；冲突自动改名语义实测；沙箱零残留。测试 98→104。
- **feat(cli)**: `cp`/`mv` 多源批量参数（BK-0018）。源参数升级 `nargs='+'`：多源时目标必须为已存在目录（或尾斜杠），逐源取 basename 组批走既有 batch 基建（50 项/批 + 逐项 errno 校验）；新增 `_require_dest_dir` 目录语义校验，不满足输出错误并退出码 1 不发请求；单源双语义（入内保名 / 改名）逐字保留。真网盘沙箱批量 mv/cp 实测对账一致、负例退出码 1、零残留。测试 76→81。
- **feat(cli)**: 递归目录树遍历与本地索引（BK-0019）。`FileManager.walk` DFS 先序递归，返回 `(depth, entry)` 与不可读目录错误清单（单点失败降级可观测不中断）；`tree` 命令树形渲染 + `--depth` 限深 + `--index` 落地全字段保真 JSON 索引（version/root/stats/errors/entries），存在读取失败退出码 1 标记结果不完整。实测发现 SDK `xpanfilelistall` 对本应用所有路径返回 `errno=20020`（应用权限级限制，含应用自建目录），引擎改用已验证的 `xpanfilelist` 客户端侧递归。真网盘 L2：`/影视/电影` 全树 2290 条（351 目录/1939 文件/6.6TB）零失败 1m44s，索引落地回读校验通过。测试 69→76。
- **feat(cli)**: 关键词搜索网盘文件（BK-0020）。`FileManager.search` 封装 `xpanfilesearch`（`--dir` 限定目录 / `--no-recursion` / page-num 分页）；`search` 命令输出完整路径与类型/大小统计，本页打满提示翻页。实测全盘命中方案 A 规范目录；发现服务端忽略 `num` 参数（单页整量返回）。测试 62→69。
- **feat(cli)**: 网盘容量与账户信息查询（BK-0022）。新增 `AccountClient`（`account.py`）封装 `UserinfoApi.apiquota`/`xpannasuinfo`，SDK 模型对象经 `to_dict`/`attribute_map` 归一化；`quota` 命令（`--check-expire`/`--check-free`、使用率与会员到期格式化）与 `whoami` 命令（账号/网盘名/会员类型）。真网盘 L2 只读实测输出正确。测试 52→62。
- **docs(backlog)**: BK-0017 第三阶段 `meta` 子系统划为待定（V1.3.0）——方案 A 目录名刮削已全量落地，Kodi/Emby/Jellyfin 可依目录名末尾 IMDb/TMDB ID 精准刮削；待用户/社区需求触发再立项。同批关闭 BK-0018~BK-0022（V1.4.0）。

## 2026-09-30

- **fix(cli/filemanager)**: 落地 file-ops P4 审查建议四项（BK-0013~BK-0016）。`_resolve_dest` 探测失败 fallback 补 `logger.warning`（BK-0013）；`rm` 交互确认补 `EOFError`/`KeyboardInterrupt` 守卫，非交互 stdin / Ctrl-C 视作取消退出 0（BK-0014）；`FileManager` 四原语新增 `_validate_filemanager_result` 统一逐项 `info[].errno` 校验，防顶层 0 部分失败漏报（BK-0015）；`copy` 错误文案改单项语境，去"批量复制批次 1"字样（BK-0016）。真网盘沙箱故障注入取证：部分失败信封顶层 `errno=12` + `info[].errno=-9`（混合批中有效项实际生效）、delete 缺源幂等返回 0。单元测试 42→52 全绿，测后沙箱零残留。
- **feat(cli)**: 补齐文件操作命令 `cp` / `rm` / `rename`，并修复 `mv` 无法移动改名的语义缺陷。`FileManager` 新增 `copy`/`batch_copy` 原语（复用 SDK `filemanagercopy`，50 项/批防超时）；`cp`/`mv` 目标双语义：已存在目录（或 `/` 结尾）→ 入内保名，否则按 `目标目录/新名` 改名；`rm` 支持多路径与默认交互确认（`-y` 跳过）。实测发现并修复 `xpanfilelist` 对不存在路径返回空列表导致的目标误判缺陷（改为父目录条目 `path`/`isdir` 精确匹配）。单元测试 28→42 全绿；真网盘沙箱 `/bdpan-cli-devtest/` 全链路实测（mkdir/cp/rename/mv/rm）通过，逐步 `ls` 对账严格守恒，测后零残留。

## 2026-09-29

- **chore(rebrand)**: 项目全面重新定位并更名为 `bdpan-cli`，提供终端命令 `bdpan`（保留 `bdpan-cli` 与 `bd-net-disc-mgr` 别名兼容）。Python 源码包重构为 `bdpan_cli`，更新内部导入路径、pyproject.toml 与相关文档引用。
- **feat**: 完成媒体库全量终态拓扑归集与种子归类。将 `/影视/电影/unscraped` 下的电影规整移入 `/影视/电影/watched`（其中 15 部整目录迁入，1 部《唐朝豪放女》zip 压缩包无缝合并入现有目录，资产零冲突零丢失）；将 `/影视/电影/pending_triage` 正式重命名为 `/影视/电影/torrents`。媒体库最终合规电影总数达 302 部（`watched` 266 部 + `unwatched` 36 部），方案 A 规范符合度 100%。
- **feat**: 构建统一工程化命令行工具 `bd-net-disc-mgr`（子命令涵盖 `ls`, `mkdir`, `mv`, `scrape preview/apply/foldering`, 以及 `meta` 元数据骨架）。实现 `scrape foldering` 散落媒体文件自动规整：创建 `/影视/电影/unscraped` 目录，将 17 个散落视频与压缩包原子移入并自动匹配 TMDB 方案 A 规范目录，成功创建 16 个规范电影目录并归集文件。全库合规电影目录数达到 303 部（`unwatched` 36 + `watched` 251 + `unscraped` 16，合规率 100%）。
- **feat**: 完成特殊条目解耦与分类治理。将 `Scario(1-2)` 拆分为《边境杀手》(2015) 与《边境杀手2：边境战士》(2018) 独立方案 A 规范目录，各视频与字幕文件原子迁移；将 `Seed.Bank.20120430-JOKER` 种子包归集至 `pending_triage`。全库 287 部电影（`unwatched` 36部 + `watched` 251部）目录名规范符合度达到 100%。
- **feat**: 完成 `/影视/电影/watched` 目录下 251 部电影的方案 A 刮削与网盘批量更名。自动识别并排除 99 部已合规目录，对 150 部电影执行精准刮削与网盘原子批量重命名（成功率 100%），实现同名多版本消歧与年份精准匹配，全网盘电影条目数严格守恒（321项）。
- **feat**: 编写 `MovieScraper` 刮削器与 `apply_scrape_rename` 执行器，支持方案 A 命名规范（`{中文名}.{英文原名}.{年份}.{imdb_id}`），通过精确标题权重、TMDB translations 与豆瓣中文补全优化匹配，对 `/影视/电影/unwatched` 目录下 36 部电影完成目录名刮削与网盘批量更名（提交 31 项更名，5 项原已规范，成功率 100%，对账严格守恒）。
- **feat**: 封装 `FileManager` 文件与目录管理能力（创建目录、重命名、分批移动、全量遍历），实测完成 `/影视/电影` 目录规范化规整（`0_notWatch` 重命名为 `unwatched`，251 个电影目录归档至 `watched`，34 个种子/压缩包/散落文件归集至 `pending_triage`，对账条目数 100% 守恒）。
- **docs V1.1.0**：更新 SDK 参考基线，补充实测核实的 `filemanagerrename`、`filemanagermove` 与 `xpanfilecreate` 参数及响应规格。
- **docs V1.0.0**：建立 doc-governance 文档治理体系（Diátaxis 四象限），发布《百度网盘开放平台 SDK 接口参考》基线（6 类 19 接口、服务器分配、参数规格、错误信封）。
- **feat**（`82100b1`）：设备码授权 + token 缓存自动续期 + 目录列表 CLI。实测通过：真实授权并列出网盘根目录 15 项。
- **chore**（`a7d3517`）：uv 项目初始化；官方 `openapi_client` SDK 以 vendor 包 `baidu-pan-sdk` 集成（来源 baidu-netdisk/mcp，MIT）。
