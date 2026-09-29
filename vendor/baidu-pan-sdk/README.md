# baidu-pan-sdk（vendor）

百度网盘开放平台官方 Python SDK（`openapi_client`，OpenAPI 文档版本 0.1，`__version__ = 1.0.0`）的原样副本。

## 来源

- 官方文档：https://pan.baidu.com/union/doc/sdk/python/python-sdk使用入门/
- 官方下载入口是一个带 JS 反爬验证的 zip 链接（`pan.baidu.com/union/challenge/dataset?competition_id=1&code=2674928287`），命令行环境无法直接下载。
- 因此从百度官方 GitHub 组织的仓库 [baidu-netdisk/mcp](https://github.com/baidu-netdisk/mcp)（`src/baidu-netdisk/openapi_client/`，MIT License）提取同一份官方 SDK 源码，目录结构与官方文档描述完全一致。

## 集成方式

符合官方文档的建议："将 `openapi_client/` 文件夹的内容复制到自己的代码库中，即可完成集成进行使用。" 本目录将其封装为本地包 `baidu-pan-sdk`，由根项目通过 `[tool.uv.sources]` 以路径依赖方式引用。

SDK 覆盖的官方接口：授权（AuthApi：授权码/设备码模式、刷新 token）、文件信息（FileinfoApi：列表/文档/图片/搜索）、文件管理（FilemanagerApi：复制/删除/移动/重命名）、文件上传（FileuploadApi：预上传/分片上传/创建文件）、递归列表与元信息（MultimediafileApi）、用户信息（UserinfoApi：容量/用户信息）。

> 除必要修复外，请勿大改本目录代码，保持与官方源码可对照。
