"""命令行入口：列出网盘目录。"""

import sys

import openapi_client
from openapi_client.api.fileinfo_api import FileinfoApi
from openapi_client.rest import ApiException

from bd_net_disc_mgr.auth import TokenManager
from bd_net_disc_mgr.config import load_config


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "/"
    config = load_config()
    access_token = TokenManager(config).get_access_token()
    with openapi_client.ApiClient() as api_client:
        try:
            response = FileinfoApi(api_client).xpanfilelist(
                access_token, dir=path, limit=100, web="1", order="name"
            )
        except ApiException as e:
            raise RuntimeError(f"读取目录失败：{e.status} {e.body}") from e
    entries = response.get("list", [])
    print(f"目录 {path} 共 {len(entries)} 项：")
    for item in entries:
        kind = "目录" if item.get("isdir") == 1 else "文件"
        size = "" if item.get("isdir") == 1 else f"{item.get('size', 0)} B"
        print(f"  [{kind}] {item.get('server_filename')} {size}".rstrip())
