# 待办与后续方向 (Backlog)

## 进行中

- [ ] 电影元数据与封面海报统一抓取：针对已完成方案 A 规范化更名的全部电影目录统一抓取并生成 `movie.nfo` 与 `poster.jpg`

## 计划中


- [ ] 递归遍历网盘文件树（`MultimediafileApi.xpanfilelistall`）并落地本地索引
- [ ] 文件搜索 CLI（`FileinfoApi.xpanfilesearch`）
- [ ] 文件上传（预上传 → 分片 → 创建，`FileuploadApi`）
- [ ] 网盘容量与用户信息查询（`UserinfoApi`）
- [ ] 文档治理体系落地：tutorials / how-to / explanation 象限按需填充

## 已关闭

- [x] 媒体库终态拓扑规整（`unscraped` 电影并入 `watched`，`pending_triage` 更名为 `torrents`，全库 302 部电影 100% 达标，2026-09-29）
- [x] 工程化统一 CLI 工具构建与 `scrape foldering` 落地（实现 `bd-net-disc-mgr` 统一子命令体系，完成 `/影视/电影/unscraped` 17个散落文件建目录与规整，2026-09-29）
- [x] 特殊条目解耦与分类（`Scario(1-2)` 拆分为边境杀手 1 与 2，`Seed.Bank` 归集至 `pending_triage`，2026-09-29）
- [x] 电影目录名方案 A 规范化刮削与批量更名（`unwatched` 36部 + `watched` 251部，全量 287 部 100% 达标，2026-09-29）
- [x] 电影目录结构规整第一步（`unwatched` 重命名、`watched` 归档、`pending_triage` 杂项归集，2026-09-29）
- [x] 文件管理核心能力封装（`FileManager`: mkdir / rename / batch_move / list_dir，2026-09-29）
- [x] 官方 Python SDK 获取与集成（vendor 包 `baidu-pan-sdk`，2026-09-29）
- [x] 设备码授权与 token 缓存（`auth.py` TokenManager，2026-09-29）
- [x] 目录列表 CLI（2026-09-29）
- [x] SDK 接口参考文档基线（2026-09-29）

