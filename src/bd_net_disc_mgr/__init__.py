"""命令行入口：列出网盘目录。"""

import sys

import openapi_client
from openapi_client.api.fileinfo_api import FileinfoApi
from openapi_client.rest import ApiException

from bd_net_disc_mgr.auth import TokenManager
from bd_net_disc_mgr.config import load_config


from bd_net_disc_mgr.cli import main

__all__ = ["main"]
