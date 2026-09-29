# 变更日志 (Changelog)

> 记录每次交付的功能与文档演进。格式：日期 + 版本 + 变更摘要。

## 2026-09-29

- **feat**: 构建统一工程化命令行工具 `bd-net-disc-mgr`（子命令涵盖 `ls`, `mkdir`, `mv`, `scrape preview/apply/foldering`, 以及 `meta` 元数据骨架）。实现 `scrape foldering` 散落媒体文件自动规整：创建 `/影视/电影/unscraped` 目录，将 17 个散落视频与压缩包原子移入并自动匹配 TMDB 方案 A 规范目录，成功创建 16 个规范电影目录并归集文件。全库合规电影目录数达到 303 部（`unwatched` 36 + `watched` 251 + `unscraped` 16，合规率 100%）。
- **feat**: 完成特殊条目解耦与分类治理。将 `Scario(1-2)` 拆分为《边境杀手》(2015) 与《边境杀手2：边境战士》(2018) 独立方案 A 规范目录，各视频与字幕文件原子迁移；将 `Seed.Bank.20120430-JOKER` 种子包归集至 `pending_triage`。全库 287 部电影（`unwatched` 36部 + `watched` 251部）目录名规范符合度达到 100%。
- **feat**: 完成 `/影视/电影/watched` 目录下 251 部电影的方案 A 刮削与网盘批量更名。自动识别并排除 99 部已合规目录，对 150 部电影执行精准刮削与网盘原子批量重命名（成功率 100%），实现同名多版本消歧与年份精准匹配，全网盘电影条目数严格守恒（321项）。
- **feat**: 编写 `MovieScraper` 刮削器与 `apply_scrape_rename` 执行器，支持方案 A 命名规范（`{中文名}.{英文原名}.{年份}.{imdb_id}`），通过精确标题权重、TMDB translations 与豆瓣中文补全优化匹配，对 `/影视/电影/unwatched` 目录下 36 部电影完成目录名刮削与网盘批量更名（提交 31 项更名，5 项原已规范，成功率 100%，对账严格守恒）。
- **feat**: 封装 `FileManager` 文件与目录管理能力（创建目录、重命名、分批移动、全量遍历），实测完成 `/影视/电影` 目录规范化规整（`0_notWatch` 重命名为 `unwatched`，251 个电影目录归档至 `watched`，34 个种子/压缩包/散落文件归集至 `pending_triage`，对账条目数 100% 守恒）。
- **docs V1.1.0**：更新 SDK 参考基线，补充实测核实的 `filemanagerrename`、`filemanagermove` 与 `xpanfilecreate` 参数及响应规格。
- **docs V1.0.0**：建立 doc-governance 文档治理体系（Diátaxis 四象限），发布《百度网盘开放平台 SDK 接口参考》基线（6 类 19 接口、服务器分配、参数规格、错误信封）。
- **feat**（`82100b1`）：设备码授权 + token 缓存自动续期 + 目录列表 CLI。实测通过：真实授权并列出网盘根目录 15 项。
- **chore**（`a7d3517`）：uv 项目初始化；官方 `openapi_client` SDK 以 vendor 包 `baidu-pan-sdk` 集成（来源 baidu-netdisk/mcp，MIT）。
