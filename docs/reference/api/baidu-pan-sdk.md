# 百度网盘开放平台 SDK 接口参考 (Technical Reference)

> **文档控制信息**
> - **文档标识**: REF-BAIDU-PAN-SDK-2026
> - **当前版本**: V1.0.0
> - **文档状态**: Active
> - **生效日期**: 2026-09-29
> - **文档所有者**: AI Agent / 工程师

---

### 修订历史记录 (Revision History)

| 版本号 | 修订日期 | 修订人 | 审核人 | 修订描述 |
| :--- | :--- | :--- | :--- | :--- |
| **V1.1.0** | 2026-09-29 | AI Agent | 架构师 | 实测核实并记录 filemanagerrename、filemanagermove 与 xpanfilecreate(mkdir) 规格 |
| **V1.0.0** | 2026-09-29 | AI Agent | 架构师 | 依据官方 SDK 文档与 vendored 源码建立接口参考基线 |

---

> ⚠️ **机器真理源声明**: 本文档为百度网盘开放平台 Python SDK 在本仓库内的权威机械规格唯一事实来源，供 AI 智能体生成代码与人机对齐使用。依据官方 SDK 文档（更新时间 2022-06-16）与 vendored SDK 源码（`__version__ = 1.0.0`）整理。

## 1. 总览与官方入口

- 官方文档中心：https://pan.baidu.com/union/doc/
- Python SDK 使用入门：https://pan.baidu.com/union/doc/sdk/python/python-sdk使用入门/
- 本仓库 SDK 载体：vendor 包 `baidu-pan-sdk`（可编辑路径依赖，见 [vendor README](../../../vendor/baidu-pan-sdk/README.md)）

SDK 覆盖 6 个 API 类、19 个接口，统一携带固定查询参数 `openapi=xpansdk`；除授权接口外均需以 query 参数传递 `access_token`。

### 1.1 服务器地址分配（来自 SDK 内置 servers 配置）

| API 类 | Base URL |
| :--- | :--- |
| AuthApi | `https://openapi.baidu.com` |
| FileinfoApi / FilemanagerApi / FileuploadApi / MultimediafileApi / UserinfoApi | `https://pan.baidu.com` |

## 2. 接口清单（19 个）

### 2.1 AuthApi（授权）

| 接口功能 | 类 | 方法 | HTTP 请求 |
| :--- | :--- | :--- | :--- |
| 授权码模式-用户授权码 Code 换取 Access Token 凭证 | AuthApi | oauth_token_code2token | **GET** /oauth/2.0/token?grant_type=authorization_code&openapi=xpansdk |
| 设备码模式-获取设备码、用户码 | AuthApi | oauth_token_device_code | **GET** /oauth/2.0/device/code?response_type=device_code&openapi=xpansdk |
| 设备码模式-用 Device Code 轮询换取 Access Token | AuthApi | oauth_token_device_token | **GET** /oauth/2.0/token?grant_type=device_token&openapi=xpansdk |
| 授权码模式-刷新 Access Token | AuthApi | oauth_token_refresh_token | **GET** /oauth/2.0/token?grant_type=refresh_token&openapi=xpansdk |

### 2.2 FileinfoApi（获取文件信息）

| 接口功能 | 类 | 方法 | HTTP 请求 |
| :--- | :--- | :--- | :--- |
| 获取文件信息-获取文档列表 | FileinfoApi | xpanfiledoclist | **GET** /rest/2.0/xpan/file?method=doclist&openapi=xpansdk |
| 获取文件信息-获取图片列表 | FileinfoApi | xpanfileimagelist | **GET** /rest/2.0/xpan/file?method=imagelist&openapi=xpansdk |
| 获取文件信息-获取文件列表 | FileinfoApi | xpanfilelist | **GET** /rest/2.0/xpan/file?method=list&openapi=xpansdk |
| 获取文件信息-搜索文件 | FileinfoApi | xpanfilesearch | **GET** /rest/2.0/xpan/file?method=search&openapi=xpansdk |

### 2.3 FilemanagerApi（管理文件）

| 接口功能 | 类 | 方法 | HTTP 请求 |
| :--- | :--- | :--- | :--- |
| 管理文件-文件复制 | FilemanagerApi | filemanagercopy | **POST** /rest/2.0/xpan/file?method=filemanager&opera=copy&openapi=xpansdk |
| 管理文件-文件删除 | FilemanagerApi | filemanagerdelete | **POST** /rest/2.0/xpan/file?method=filemanager&opera=delete&openapi=xpansdk |
| 管理文件-文件移动 | FilemanagerApi | filemanagermove | **POST** /rest/2.0/xpan/file?method=filemanager&opera=move&openapi=xpansdk |
| 管理文件-文件重命名 | FilemanagerApi | filemanagerrename | **POST** /rest/2.0/xpan/file?method=filemanager&opera=rename&openapi=xpansdk |

### 2.4 FileuploadApi（文件上传）

| 接口功能 | 类 | 方法 | HTTP 请求 |
| :--- | :--- | :--- | :--- |
| 文件上传-预上传 | FileuploadApi | xpanfileprecreate | **POST** /rest/2.0/xpan/file?method=precreate&openapi=xpansdk |
| 文件上传-分片上传 | FileuploadApi | pcssuperfile2 | **POST** /rest/2.0/pcs/superfile2?method=upload&openapi=xpansdk |
| 文件上传-创建文件 | FileuploadApi | xpanfilecreate | **POST** /rest/2.0/xpan/file?method=create&openapi=xpansdk |

### 2.5 MultimediafileApi（递归列表与元信息）

| 接口功能 | 类 | 方法 | HTTP 请求 |
| :--- | :--- | :--- | :--- |
| 获取文件信息-递归获取文件列表 | MultimediafileApi | xpanfilelistall | **GET** /rest/2.0/xpan/multimedia?method=listall&openapi=xpansdk |
| 获取文件信息-查询文件信息 | MultimediafileApi | xpanmultimediafilemetas | **GET** /rest/2.0/xpan/multimedia?method=filemetas&openapi=xpansdk |

### 2.6 UserinfoApi（用户与容量）

| 接口功能 | 类 | 方法 | HTTP 请求 |
| :--- | :--- | :--- | :--- |
| 获取网盘容量信息 | UserinfoApi | apiquota | **GET** /api/quota?openapi=xpansdk |
| 获取用户信息 | UserinfoApi | xpannasuinfo | **GET** /rest/2.0/xpan/nas?method=uinfo&openapi=xpansdk |

## 3. 本仓库代码映射

| API 类 | SDK 源码路径 | 响应模型 |
| :--- | :--- | :--- |
| AuthApi | `vendor/baidu-pan-sdk/openapi_client/api/auth_api.py` | `model/oauth_token_*.py` |
| FileinfoApi | `vendor/baidu-pan-sdk/openapi_client/api/fileinfo_api.py` | `dict`（`list` 字段为条目数组） |
| FilemanagerApi | `vendor/baidu-pan-sdk/openapi_client/api/filemanager_api.py` | `dict` |
| FileuploadApi | `vendor/baidu-pan-sdk/openapi_client/api/fileupload_api.py` | `dict` |
| MultimediafileApi | `vendor/baidu-pan-sdk/openapi_client/api/multimediafile_api.py` | `dict` |
| UserinfoApi | `vendor/baidu-pan-sdk/openapi_client/api/userinfo_api.py` | `model/quotaresponse.py`、`model/uinforesponse.py` |

### 3.1 已核实的参数与响应规格

已知事实（源码核实）：`xpanfilelist` 查询参数为 `access_token`（必填）、`dir`、`folder`、`start`（必须为 str 类型）、`limit`、`order`、`desc`、`web`、`showempty`；返回 dict，条目数组位于 `list` 键，条目字段含 `fs_id`、`path`、`server_filename`、`size`、`isdir`（1 为目录）。

已知事实（实测核实）：`filemanagerrename` 参数 `_async=0`，`filelist` 为 JSON 字符串 `[{"path": "/old/path", "newname": "new_name"}]`；成功返回 `{"errno": 0, "info": [{"errno": 0, "path": "...", "to_path": "..."}]}`。

已知事实（实测核实）：`filemanagermove` 参数 `_async=0`，`filelist` 为 JSON 字符串 `[{"path": "/src/path", "dest": "/dest/dir", "newname": "name"}]`；成功返回 `{"errno": 0, "info": [...]}`。支持批量（建议每批 ≤50 项以防超时）。

已知事实（实测核实）：`xpanfilecreate` 用于创建目录时，参数为 `access_token`、`path`、`isdir=1`、`size=0`、`uploadid=""`、`block_list="[]"`、`rtype=1`；若目录已存在，API 返回 `{"errno": -8}`。

已知事实（源码核实）：`oauth_token_device_code` 必填参数为 `client_id`、`scope`；响应模型 `OauthTokenDeviceCodeResponse` 字段为 `device_code`、`user_code`、`verification_url`、`qrcode_url`、`expires_in`、`interval`。`oauth_token_device_token` 必填参数为 `code`（即 device_code）、`client_id`、`client_secret`；响应字段为 `access_token`、`refresh_token`、`expires_in`、`session_key`、`session_secret`、`scope`。

已知事实（实测核实）：本仓库 `TokenManager`（[auth.py](../../../src/bdpan_cli/auth.py)）以 scope=`basic,netdisk` 走设备码模式，access_token 有效期 30 天，refresh_token 有效期 10 年。


## 4. 错误信封

OAuth 授权类接口失败返回：

```json
{"error": "authorization_pending", "error_description": "..."}
```

常见 `error` 值：`authorization_pending`（用户尚未确认，继续轮询）、`slow_down`（轮询过快，需加大间隔）、`expired_token`（设备码过期）。

xpan 业务接口失败返回：

```json
{"errno": 0, "errmsg": "..."}
```

`errno=0` 表示成功。常见非零值：`2`（权限不足）、`-6`（身份验证失败，access_token 无效）、`111`（access_token 过期）。完整错误码见官方文档错误码页面（https://pan.baidu.com/union/doc/）。
