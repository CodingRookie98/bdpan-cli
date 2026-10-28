"""命令行入口：列出网盘目录。"""

import sys

from bdpan_cli._vendor import openapi_client
from bdpan_cli._vendor.openapi_client.api.fileinfo_api import FileinfoApi
from bdpan_cli._vendor.openapi_client.rest import ApiException

from bdpan_cli.auth import TokenManager
from bdpan_cli.config import load_config


from bdpan_cli.cli import main

__all__ = ["main"]
