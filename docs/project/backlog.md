# 待办与后续方向 (Backlog)

## 进行中

（暂无进行中任务，准备进入第三阶段元数据与封面海报自动化生成）

## 计划中

- [ ] (P4 审查建议) `_resolve_dest` 探测失败 fallback 分支补 `logger.warning`（cli.py:89-90）
- [ ] (P4 审查建议) `rm` 交互确认补 EOFError/KeyboardInterrupt 守卫（非交互 stdin 下避免裸 traceback）
- [ ] (P4 审查建议·立项) filemanager 四原语（copy/move/rename/rename）逐项 `info[].errno` 校验统一加固——待真网盘故障注入取证后实施
- [ ] (P4 审查建议) `FileManager.copy` 错误文案去掉"批量复制批次 1"字样
- [ ] 第三阶段：电影元数据与封面海报全量自动化生成与上传 (`meta` 子系统)
  - [ ] `bdpan meta nfo <dir>`：依据方案 A 目录名末尾的 IMDb/TMDB ID，精准查询 TMDB 电影详情并生成符合 Kodi/Emby/Jellyfin 格式的 `movie.nfo`（支持评分、演职员、分级、标签、中文简介等）
  - [ ] `bdpan meta poster <dir>`：下载 TMDB 最高清竖版官方海报，流式调用百度网盘上传接口写入各电影根目录的 `poster.jpg`
  - [ ] 支持断点续传、已存在跳过（幂等性）与 `--dry-run` 预览模式
  - [ ] 对 `/影视/电影/watched`（266部）与 `/影视/电影/unwatched`（36部）共 302 部电影全量批处理
- [ ] 文件操作命令多源批量参数（`cp`/`mv`/`rm` 批量语义，方案 B 残余项）
- [ ] 递归遍历网盘文件树（`MultimediafileApi.xpanfilelistall`）并落地本地索引
- [ ] 文件搜索 CLI（`FileinfoApi.xpanfilesearch`）
- [ ] 大文件分片上传与断点续传（预上传 → 分片 → 创建，`FileuploadApi`）
- [ ] 网盘容量与用户信息查询（`UserinfoApi`）
- [ ] 文档治理体系落地：tutorials / how-to / explanation 象限按需填充

## 已关闭

- [x] 文件操作命令补齐：新增 `cp`/`rm`/`rename`，修复 `mv` 移动改名语义（`FileManager.copy`/`batch_copy`，真网盘沙箱全链路实测通过，2026-09-30）
- [x] 项目全面重新定位与品牌重命名：重命名为 `bdpan-cli`，主命令 `bdpan`（完成代码包迁移、pyproject.toml、CLI 别名与全量测试，2026-09-29）
- [x] 媒体库终态拓扑规整（`unscraped` 电影并入 `watched`，`pending_triage` 更名为 `torrents`，全库 302 部电影 100% 达标，2026-09-29）
- [x] 工程化统一 CLI 工具构建与 `scrape foldering` 落地（实现统一子命令体系，完成 `/影视/电影/unscraped` 17个散落文件建目录与规整，2026-09-29）
- [x] 特殊条目解耦与分类（`Scario(1-2)` 拆分为边境杀手 1 与 2，`Seed.Bank` 归集至 `pending_triage`，2026-09-29）
- [x] 电影目录名方案 A 规范化刮削与批量更名（`unwatched` 36部 + `watched` 251部，全量 287 部 100% 达标，2026-09-29）
- [x] 电影目录结构规整第一步（`unwatched` 重命名、`watched` 归档、`pending_triage` 杂项归集，2026-09-29）
- [x] 文件管理核心能力封装（`FileManager`: mkdir / rename / batch_move / list_dir，2026-09-29）
- [x] 官方 Python SDK 获取与集成（vendor 包 `baidu-pan-sdk`，2026-09-29）
- [x] 设备码授权与 token 缓存（`auth.py` TokenManager，2026-09-29）
- [x] 目录列表 CLI（2026-09-29）
- [x] SDK 接口参考文档基线（2026-09-29）

