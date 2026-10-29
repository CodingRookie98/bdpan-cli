"""BaiduPan: 百度网盘高层开发者客户端 (Python SDK 统一门面)。

提供开箱即用、类型友好且统一封装的 Python 开发者 API，聚合文件增删改查、秒传/分片上传、
断点续传下载、多账号隔离、媒体深度元数据探测及容量账户查询等全量能力。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from bdpan_cli.account import AccountClient
from bdpan_cli.auth import TokenManager
from bdpan_cli.config import AppConfig, load_config
from bdpan_cli.downloader import Downloader
from bdpan_cli.file_manager import FileManager
from bdpan_cli.media_info import MediaInfoClient
from bdpan_cli.uploader import Uploader


class BaiduPan:
    """百度网盘高层开发者客户端 (Python SDK)。

    使用示例:
        ```python
        from bdpan_cli import BaiduPan

        # 1. 自动从环境变量、当前目录 .env 或 ~/.config/bdpan/.env 初始化
        pan = BaiduPan()

        # 或通过显式凭据/Token 初始化
        pan = BaiduPan(app_key="...", secret_key="...")
        pan = BaiduPan(access_token="...")

        # 2. 浏览与文件操作
        files = pan.list_dir("/影视/电影")
        pan.mkdir("/影视/电影/新分类")
        pan.rename("/影视/电影/old.mkv", "new.mkv")

        # 3. 极速秒传与断点续传上传
        res = pan.upload("local.mkv", remote_dir="/影视/电影")

        # 4. 断点续传下载
        local_path = pan.download("/影视/电影/Inception.mkv", dest_dir="./downloads")

        # 5. 视频媒体深度元数据
        info = pan.get_media_info("/影视/电影/Inception.mkv")
        print(f"分辨率: {info['resolution']}, 时长: {info['duration']}")
        ```
    """

    def __init__(
        self,
        app_key: str | None = None,
        secret_key: str | None = None,
        access_token: str | None = None,
        account: str | None = None,
        config: AppConfig | None = None,
        cache_path: str | Path | None = None,
    ) -> None:
        self._explicit_token = access_token
        self._account = account
        self._cache_path = Path(cache_path) if cache_path else None

        # 延迟初始化的底层客户端缓存
        self._files: FileManager | None = None
        self._uploader: Uploader | None = None
        self._downloader: Downloader | None = None
        self._account_client: AccountClient | None = None
        self._media_client: MediaInfoClient | None = None

        if self._explicit_token:
            self._config = config or AppConfig(
                app_key=app_key or "explicit_token_app_key",
                secret_key=secret_key or "explicit_token_secret_key",
            )
            self._token_manager: TokenManager | None = None
        else:
            if app_key and secret_key:
                self._config = AppConfig(app_key=app_key, secret_key=secret_key)
            elif config:
                self._config = config
            else:
                self._config = load_config()

            self._token_manager = TokenManager(
                self._config,
                account=self._account,
                cache_path=self._cache_path,
            )

    @property
    def access_token(self) -> str:
        """获取当前生效的 access_token（自动在临期时静默刷新）。"""
        if self._explicit_token:
            return self._explicit_token
        assert self._token_manager is not None
        return self._token_manager.get_access_token()

    @property
    def token_manager(self) -> TokenManager | None:
        """获取底层 TokenManager 凭据管理器实例。"""
        return self._token_manager

    # ------------------------------------------------------------------
    # 底层专用 Client 属性访问（支持高阶或深度定制控制）
    # ------------------------------------------------------------------

    @property
    def files(self) -> FileManager:
        """获取底层 FileManager 文件管理客户端。"""
        if self._files is None:
            self._files = FileManager(self.access_token)
        return self._files

    @files.setter
    def files(self, value: FileManager) -> None:
        self._files = value

    @files.deleter
    def files(self) -> None:
        self._files = None

    @property
    def uploader(self) -> Uploader:
        """获取底层 Uploader 上传客户端。"""
        if self._uploader is None:
            self._uploader = Uploader(self.access_token)
        return self._uploader

    @uploader.setter
    def uploader(self, value: Uploader) -> None:
        self._uploader = value

    @uploader.deleter
    def uploader(self) -> None:
        self._uploader = None

    @property
    def downloader(self) -> Downloader:
        """获取底层 Downloader 下载客户端。"""
        if self._downloader is None:
            self._downloader = Downloader(self.access_token)
        return self._downloader

    @downloader.setter
    def downloader(self, value: Downloader) -> None:
        self._downloader = value

    @downloader.deleter
    def downloader(self) -> None:
        self._downloader = None

    @property
    def account(self) -> AccountClient:
        """获取底层 AccountClient 账户与配额客户端。"""
        if self._account_client is None:
            self._account_client = AccountClient(self.access_token)
        return self._account_client

    @account.setter
    def account(self, value: AccountClient) -> None:
        self._account_client = value

    @account.deleter
    def account(self) -> None:
        self._account_client = None

    @property
    def media(self) -> MediaInfoClient:
        """获取底层 MediaInfoClient 媒体元数据客户端。"""
        if self._media_client is None:
            self._media_client = MediaInfoClient(self.access_token)
        return self._media_client

    @media.setter
    def media(self, value: MediaInfoClient) -> None:
        self._media_client = value

    @media.deleter
    def media(self) -> None:
        self._media_client = None

    # ------------------------------------------------------------------
    # 高层核心便捷 API: 文件与目录操作
    # ------------------------------------------------------------------

    def list_dir(self, dir_path: str = "/", limit: int = 1000) -> list[dict[str, Any]]:
        """列出指定网盘目录下的文件与子目录列表。"""
        return self.files.list_dir(dir_path=dir_path, limit=limit)

    def ls(self, dir_path: str = "/", limit: int = 1000) -> list[dict[str, Any]]:
        """list_dir 的别名简写。"""
        return self.list_dir(dir_path=dir_path, limit=limit)

    def get_file_info(self, path: str) -> dict[str, Any] | None:
        """获取单个网盘文件的详细元数据（若不存在返回 None）。"""
        return self.files.get_file_info(path)

    def search(self, key: str, dir_path: str = "/", recursion: int = 1) -> list[dict[str, Any]]:
        """在网盘指定目录下递归或非递归搜索包含关键词的文件。"""
        return self.files.search(key=key, dir_path=dir_path, recursion=recursion)

    def mkdir(self, path: str) -> dict[str, Any]:
        """在网盘上递归创建目录。"""
        return self.files.mkdir(path)

    def rename(self, path: str, new_name: str) -> dict[str, Any]:
        """对网盘上的单个文件或目录执行原地重命名。"""
        return self.files.rename(path=path, new_name=new_name)

    def move(self, src: str | list[str], dest: str) -> dict[str, Any]:
        """移动文件或目录。

        - 单文件移动:
          - 若 dest 以 '/' 结尾或为目录: 保留原文件名移入该目录
          - 若 dest 指向新路径: 移动并重命名为 dest 指定的文件名
        - 批量移动: 将 src 列表中的所有文件统一移动至 dest 目录下
        """
        if isinstance(src, str):
            src_name = Path(src).name
            if dest.endswith("/"):
                dest_dir = dest.rstrip("/") or "/"
                new_name = src_name
            else:
                dest_dir = str(Path(dest).parent)
                new_name = Path(dest).name
            return self.files.batch_move([{"path": src, "dest": dest_dir, "newname": new_name}])

        # 批量模式
        dest_dir = dest.rstrip("/") or "/"
        filelist = [{"path": s, "dest": dest_dir, "newname": Path(s).name} for s in src]
        return self.files.batch_move(filelist)

    def mv(self, src: str | list[str], dest: str) -> dict[str, Any]:
        """move 的别名简写。"""
        return self.move(src=src, dest=dest)

    def copy(self, src: str | list[str], dest: str, new_name: str | None = None) -> dict[str, Any]:
        """复制文件或目录。

        - 单文件复制:
          - 支持显式指定 new_name
          - 未指定 new_name 时若 dest 包含文件名则自动提取，否则沿用原名
        - 批量复制: 将 src 列表中的所有文件复制至 dest 目录下
        """
        if isinstance(src, str):
            src_name = Path(src).name
            if new_name:
                return self.files.copy(path=src, dest_dir=dest.rstrip("/") or "/", new_name=new_name)

            if dest.endswith("/"):
                dest_dir = dest.rstrip("/") or "/"
                target_name = src_name
            else:
                dest_dir = str(Path(dest).parent)
                target_name = Path(dest).name
            return self.files.copy(path=src, dest_dir=dest_dir, new_name=target_name)

        # 批量模式
        dest_dir = dest.rstrip("/") or "/"
        filelist = [{"path": s, "dest": dest_dir, "newname": Path(s).name} for s in src]
        return self.files.batch_copy(filelist)

    def cp(self, src: str | list[str], dest: str, new_name: str | None = None) -> dict[str, Any]:
        """copy 的别名简写。"""
        return self.copy(src=src, dest=dest, new_name=new_name)

    def delete(self, path: str | list[str]) -> dict[str, Any]:
        """删除网盘文件或目录（服务端自动移入回收站）。支持单个路径或路径列表（50项批量保护）。"""
        if isinstance(path, str):
            return self.files.delete(path)
        return self.files.batch_delete(path)

    def rm(self, path: str | list[str]) -> dict[str, Any]:
        """delete 的别名简写。"""
        return self.delete(path=path)

    def tree(self, path: str = "/", max_depth: int | None = None) -> list[dict[str, Any]]:
        """递归遍历网盘目录树并返回打平后的所有文件与目录元数据清单。"""
        all_items, _ = self.files.walk(root=path, max_depth=max_depth)
        return [item for _, item in all_items]

    # ------------------------------------------------------------------
    # 高层核心便捷 API: 传输（上传与下载）
    # ------------------------------------------------------------------

    def upload(
        self,
        local_path: str | Path,
        remote_dir: str = "/",
        remote_filename: str | None = None,
        overwrite: bool = False,
        state_file: str | Path | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """上传本地文件至网盘（支持秒传、动态机房调度、多分片与断点续传）。

        Args:
            local_path: 本地待上传文件路径
            remote_dir: 网盘目标目录（如 /影视/电影）
            remote_filename: 网盘目标文件名（默认与本地文件同名）
            overwrite: 若远程文件已存在是否直接覆盖（False 则服务端报错冲突）
            state_file: 断点续传状态持久化文件路径（默认保存在 token 目录同级）
            on_progress: 进度回调函数，签名 callback(uploaded_bytes, total_bytes)

        Returns:
            服务端创建成功的完整文件元数据字典
        """
        return self.uploader.upload(
            local_path=local_path,
            remote_dir=remote_dir,
            remote_filename=remote_filename,
            overwrite=overwrite,
            state_file=state_file,
            on_progress=on_progress,
        )

    def download(
        self,
        remote_path: str,
        dest_dir: str | Path = "./",
        overwrite: bool = False,
        chunk_size: int = 4 * 1024 * 1024,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """断点续传下载网盘文件至本地目录。

        Args:
            remote_path: 网盘文件完整绝对路径
            dest_dir: 本地存放目录（默认当前目录）
            overwrite: 本地若存在同名已完成文件是否强制覆盖
            chunk_size: 下载分块缓冲大小（默认 4MB）
            on_progress: 进度回调函数，签名 callback(downloaded_bytes, total_bytes)

        Returns:
            下载完成后的本地 Path 对象
        """
        return self.downloader.download_file(
            remote_path=remote_path,
            dest_dir=dest_dir,
            overwrite=overwrite,
            chunk_size=chunk_size,
            on_progress=on_progress,
        )

    def get_download_url(self, remote_path: str) -> str:
        """获取指定网盘文件的高速直链下载真实 URL (dlink)。"""
        res = self.downloader.get_dlink(remote_path)
        dlink = res.get("dlink")
        if not dlink:
            raise RuntimeError(f"未能提取到有效直链: {res}")
        return str(dlink)

    # ------------------------------------------------------------------
    # 高层核心便捷 API: 媒体元数据与聚合统计
    # ------------------------------------------------------------------

    def get_media_info(self, remote_path: str) -> dict[str, Any]:
        """探测视频文件的深度元数据（精准分辨率 4K/1080P、时长 HH:MM:SS、HEVC/H.264 编码与音轨）。"""
        return self.media.get_media_info(remote_path=remote_path)

    def get_dir_stats(self, remote_path: str = "/", max_depth: int | None = None) -> dict[str, Any]:
        """递归聚合统计目录总容量、总文件数及媒体格式分类占比。"""
        return self.media.get_dir_stats(remote_path=remote_path, max_depth=max_depth)

    # ------------------------------------------------------------------
    # 高层核心便捷 API: 账户与配额查询
    # ------------------------------------------------------------------

    def whoami(self) -> dict[str, Any]:
        """查询当前登录网盘用户的基本信息（百度用户名、头像、UID、VIP等级等）。"""
        return self.account.user_info()

    def get_quota(self, check_expire: bool = False, check_free: bool = False) -> dict[str, Any]:
        """查询网盘总容量、已用空间与剩余空间配额。"""
        return self.account.quota(check_expire=check_expire, check_free=check_free)

    # ------------------------------------------------------------------
    # 高层核心便捷 API: 多账号管理与切换
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[dict[str, Any]]:
        """列出本地保存的所有网盘账号别名及 Token 到期状态。"""
        if not self._token_manager:
            return [{"account": "explicit_token", "is_current": True, "valid": True}]
        return self._token_manager.list_accounts()

    def switch_account(self, alias: str) -> None:
        """切换当前默认活跃的网盘账号别名。"""
        if not self._token_manager:
            raise RuntimeError("以显式 access_token 初始化的客户端不支持账号切换")
        self._token_manager.switch_account(alias)
