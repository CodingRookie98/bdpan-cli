# 变更日志 (Changelog)

> 记录每次交付的功能与文档演进。格式：日期 + 版本 + 变更摘要。

## 2026-09-29

- **文档 V1.0.0**：建立 doc-governance 文档治理体系（Diátaxis 四象限），发布《百度网盘开放平台 SDK 接口参考》基线（6 类 19 接口、服务器分配、参数规格、错误信封）。
- **feat**（`82100b1`）：设备码授权 + token 缓存自动续期 + 目录列表 CLI。实测通过：真实授权并列出网盘根目录 15 项。
- **chore**（`a7d3517`）：uv 项目初始化；官方 `openapi_client` SDK 以 vendor 包 `baidu-pan-sdk` 集成（来源 baidu-netdisk/mcp，MIT）。
