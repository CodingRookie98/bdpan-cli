# 待办与后续方向 (Backlog)

## 进行中

- [ ] 电影自动刮削体系搭建：针对 `/影视/电影/unwatched` 待看目录进行 TMDB/豆瓣元数据匹配、海报与 NFO 生成

## 计划中

- [ ] 递归遍历网盘文件树（`MultimediafileApi.xpanfilelistall`）并落地本地索引
- [ ] 文件搜索 CLI（`FileinfoApi.xpanfilesearch`）
- [ ] 文件上传（预上传 → 分片 → 创建，`FileuploadApi`）
- [ ] 网盘容量与用户信息查询（`UserinfoApi`）
- [ ] 文档治理体系落地：tutorials / how-to / explanation 象限按需填充

## 已关闭

- [x] 电影目录结构规整第一步（`unwatched` 重命名、`watched` 归档、`pending_triage` 杂项归集，2026-09-29）
- [x] 文件管理核心能力封装（`FileManager`: mkdir / rename / batch_move / list_dir，2026-09-29）
- [x] 官方 Python SDK 获取与集成（vendor 包 `baidu-pan-sdk`，2026-09-29）
- [x] 设备码授权与 token 缓存（`auth.py` TokenManager，2026-09-29）
- [x] 目录列表 CLI（2026-09-29）
- [x] SDK 接口参考文档基线（2026-09-29）

