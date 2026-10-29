"""bdpan-cli: 百度网盘工程化 CLI 管理工具与 Python 开发者 SDK。"""

from bdpan_cli.account import AccountClient, AccountError
from bdpan_cli.auth import AuthorizationNeeded, TokenManager
from bdpan_cli.client import BaiduPan
from bdpan_cli.config import (
    AppConfig,
    ConfigError,
    get_global_config_path,
    load_config,
    save_global_config,
)
from bdpan_cli.downloader import DownloadError, Downloader
from bdpan_cli.file_manager import FileManager, FileManagerError
from bdpan_cli.media_info import MediaInfoClient, MediaInfoError
from bdpan_cli.uploader import UploadError, Uploader
from bdpan_cli._version import __version__
from bdpan_cli.cli import main

__all__ = [
    # 核心高层客户端 (Python SDK)
    "BaiduPan",
    # 专用子客户端
    "FileManager",
    "Uploader",
    "Downloader",
    "AccountClient",
    "MediaInfoClient",
    "TokenManager",
    # 常用配置与凭证
    "AppConfig",
    "load_config",
    "save_global_config",
    "get_global_config_path",
    # 核心异常类
    "ConfigError",
    "FileManagerError",
    "UploadError",
    "DownloadError",
    "AccountError",
    "MediaInfoError",
    "AuthorizationNeeded",
    # 命令行入口与版本
    "main",
    "__version__",
]
