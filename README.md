# bd-net-disc-mgr

个人百度网盘文件数据资料管理工具。基于[百度网盘开放平台](https://pan.baidu.com/union/doc/)官方 Python SDK，使用 Python + uv 构建。

## 项目结构

```
├── docs/                     # 治理文档（Diátaxis 四象限，见 docs/GOVERNANCE.md）
│   ├── index.md              # 知识库总入口
│   ├── llms.txt              # AI 智能体机器地图
│   └── reference/api/        # SDK 接口参考（机器真理源）
├── pyproject.toml            # 主项目（包 bd_net_disc_mgr，入口 bd-net-disc-mgr）
├── src/bd_net_disc_mgr/      # 业务代码
├── vendor/baidu-pan-sdk/     # 官方 openapi_client SDK 的 vendor 本地包（见其 README）
├── uv.lock
└── .python-version           # 3.12
```

## 开发环境

```bash
uv sync        # 创建 .venv 并安装依赖（含 vendor SDK）
uv run bd-net-disc-mgr
```

## 应用凭证配置

复制模板并填入开放平台应用的 AppKey / AppSecret（`.env` 已被 git 忽略，不会提交）：

```bash
cp .env.example .env
```

## 使用 SDK

SDK 以可编辑本地包 `baidu-pan-sdk` 依赖引入，直接 `import openapi_client` 即可：

```python
import openapi_client
from openapi_client.api import userinfo_api

with openapi_client.ApiClient() as api_client:
    api = userinfo_api.UserinfoApi(api_client)
    resp = api.apiquota("<access_token>", checkexpire=1, checkfree=1)
```

接入前需在[开放平台控制台](https://pan.baidu.com/union/doc/)完成：注册登录 → 实名认证 → 创建应用 → 授权获取 `access_token`（SDK 的 `AuthApi` 支持授权码模式与设备码模式）。
