"""命令行入口：列出网盘目录。"""

import sys

import openapi_client
from openapi_client.api.fileinfo_api import FileinfoApi
from openapi_client.rest import ApiException

from bdpan_cli.auth import TokenManager
from bdpan_cli.config import load_config


from bdpan_cli.cli import main

__all__ = ["main"]
