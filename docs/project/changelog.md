# 变更日志 (Changelog)

> 记录每次交付的功能与文档演进。格式：日期 + 版本 + 变更摘要。

## 2026-09-29

- **feat**: 编写 `MovieScraper` 刮削器与 `apply_scrape_rename` 执行器，支持方案 A 命名规范（`{中文名}.{英文原名}.{年份}.{imdb_id}`），通过精确标题权重、TMDB translations 与豆瓣中文补全优化匹配，对 `/影视/电影/unwatched` 目录下 36 部电影完成目录名刮削与网盘批量更名（提交 31 项更名，5 项原已规范，成功率 100%，对账严格守恒）。
- **feat**: 封装 `FileManager` 文件与目录管理能力（创建目录、重命名、分批移动、全量遍历），实测完成 `/影视/电影` 目录规范化规整（`0_notWatch` 重命名为 `unwatched`，251 个电影目录归档至 `watched`，34 个种子/压缩包/散落文件归集至 `pending_triage`，对账条目数 100% 守恒）。
- **docs V1.1.0**：更新 SDK 参考基线，补充实测核实的 `filemanagerrename`、`filemanagermove` 与 `xpanfilecreate` 参数及响应规格。
- **docs V1.0.0**：建立 doc-governance 文档治理体系（Diátaxis 四象限），发布《百度网盘开放平台 SDK 接口参考》基线（6 类 19 接口、服务器分配、参数规格、错误信封）。
- **feat**（`82100b1`）：设备码授权 + token 缓存自动续期 + 目录列表 CLI。实测通过：真实授权并列出网盘根目录 15 项。
- **chore**（`a7d3517`）：uv 项目初始化；官方 `openapi_client` SDK 以 vendor 包 `baidu-pan-sdk` 集成（来源 baidu-netdisk/mcp，MIT）。
