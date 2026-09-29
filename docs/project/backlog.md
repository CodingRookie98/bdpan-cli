# 待办与后续方向 (Backlog)

## 进行中

- [ ] 文档治理体系落地：tutorials / how-to / explanation 象限按需填充（首个候选：快速上手教程）

## 计划中

- [ ] 递归遍历网盘文件树（`MultimediafileApi.xpanfilelistall`）并落地本地索引
- [ ] 文件搜索 CLI（`FileinfoApi.xpanfilesearch`）
- [ ] 文件管理操作：复制 / 移动 / 重命名 / 删除（`FilemanagerApi`）
- [ ] 文件上传（预上传 → 分片 → 创建，`FileuploadApi`）
- [ ] 网盘容量与用户信息查询（`UserinfoApi`）

## 已关闭

- [x] 官方 Python SDK 获取与集成（vendor 包 `baidu-pan-sdk`，2026-09-29）
- [x] 设备码授权与 token 缓存（`auth.py` TokenManager，2026-09-29）
- [x] 目录列表 CLI（2026-09-29）
- [x] SDK 接口参考文档基线（2026-09-29）
