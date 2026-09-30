# 待办与后续方向 (Backlog)

> **控制信息**
> - **文档版本**: V1.1.0
> - **文档标识**: BKLG-bdpan-cli
> - **生效日期**: 2026-09-30
> - **条目规范**: [backlog-specification.md](../../.agents/skills/doc-governance/references/backlog-specification.md)

## 进行中

（暂无进行中任务，准备进入第三阶段元数据与封面海报自动化生成）

## 计划中

- [ ] BK-0013 (P4 审查建议) `_resolve_dest` 探测失败 fallback 分支补 `logger.warning`（cli.py:89-90）
- [ ] BK-0014 (P4 审查建议) `rm` 交互确认补 EOFError/KeyboardInterrupt 守卫（非交互 stdin 下避免裸 traceback）
- [ ] BK-0015 (P4 审查建议·立项) filemanager 四原语（copy/move/rename/delete）逐项 `info[].errno` 校验统一加固——待真网盘故障注入取证后实施
- [ ] BK-0016 (P4 审查建议) `FileManager.copy` 错误文案去掉"批量复制批次 1"字样
- [ ] BK-0017 第三阶段：电影元数据与封面海报全量自动化生成与上传 (`meta` 子系统)
  - [ ] `bdpan meta nfo <dir>`：依据方案 A 目录名末尾的 IMDb/TMDB ID，精准查询 TMDB 电影详情并生成符合 Kodi/Emby/Jellyfin 格式的 `movie.nfo`（支持评分、演职员、分级、标签、中文简介等）
  - [ ] `bdpan meta poster <dir>`：下载 TMDB 最高清竖版官方海报，流式调用百度网盘上传接口写入各电影根目录的 `poster.jpg`
  - [ ] 支持断点续传、已存在跳过（幂等性）与 `--dry-run` 预览模式
  - [ ] 对 `/影视/电影/watched`（266部）与 `/影视/电影/unwatched`（36部）共 302 部电影全量批处理
- [ ] BK-0018 文件操作命令多源批量参数（`cp`/`mv`/`rm` 批量语义，方案 B 残余项）
- [ ] BK-0019 递归遍历网盘文件树（`MultimediafileApi.xpanfilelistall`）并落地本地索引
- [ ] BK-0020 文件搜索 CLI（`FileinfoApi.xpanfilesearch`）
- [ ] BK-0021 大文件分片上传与断点续传（预上传 → 分片 → 创建，`FileuploadApi`）
- [ ] BK-0022 网盘容量与用户信息查询（`UserinfoApi`）
- [ ] BK-0023 文档治理体系落地：tutorials / how-to / explanation 象限按需填充

## 已关闭

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
| V1.1.0 | 2026-09-30 | 全量条目迁移 BK-0001~BK-0023 编号，补控制头，接入 backlog-specification.md 规范 |
| V1.0.0 | 2026-09-29 | 建立"进行中/计划中/已关闭"三区待办清单 |
