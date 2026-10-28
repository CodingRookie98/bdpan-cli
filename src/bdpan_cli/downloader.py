"""Downloader: 百度网盘文件直链提取与多协议/分块断点续传下载引擎。"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from bdpan_cli._vendor import openapi_client
from bdpan_cli._vendor.openapi_client.api.multimediafile_api import MultimediafileApi
from bdpan_cli._vendor.openapi_client.rest import ApiException
from bdpan_cli.file_manager import FileManager

logger = logging.getLogger(__name__)

# 官方防盗链/限速必需请求头
BAIDU_PAN_UA = "pan.baidu.com"
CHUNK_READ_SIZE = 256 * 1024  # 256KB 缓冲区


class DownloadError(RuntimeError):
    """文件下载或直链获取异常基类。"""


class Downloader:
    """网盘文件直链提取与断点续传下载器。"""

    def __init__(self, access_token: str, api_client: openapi_client.ApiClient | None = None) -> None:
        self.access_token = access_token
        self.api_client = api_client or openapi_client.ApiClient()
        self._multimedia_api = MultimediafileApi(self.api_client)
        self._file_manager = FileManager(access_token, self.api_client)

    def get_dlink(self, remote_path: str) -> dict[str, Any]:
        """获取单个网盘文件的真实下载直链 (dlink) 与元数据。

        Args:
            remote_path: 网盘文件绝对路径。

        Returns:
            条目元数据字典，包含 dlink、fs_id、size、md5、server_filename 等。

        Raises:
            DownloadError: 当文件不存在、为目录或接口返回异常时抛出。
        """
        info = self._file_manager.get_file_info(remote_path)
        if not info:
            raise DownloadError(f"网盘文件不存在: {remote_path}")
        if info.get("isdir") == 1:
            raise DownloadError(f"目标为目录，不支持直接获取直链下载: {remote_path}")

        fs_id = info["fs_id"]
        try:
            res = self._multimedia_api.xpanmultimediafilemetas(
                access_token=self.access_token,
                fsids=json.dumps([fs_id]),
                dlink="1",
            )
        except ApiException as e:
            raise DownloadError(f"获取直链 API 异常 [{remote_path}]: {e.status} {e.body}") from e

        if not isinstance(res, dict) or res.get("errno") != 0:
            raise DownloadError(f"获取直链失败 [{remote_path}]: errno={res.get('errno', '?')}")

        entries = res.get("list") or []
        if not entries:
            raise DownloadError(f"获取直链返回空列表 [{remote_path}]")

        meta = entries[0]
        if not meta.get("dlink"):
            raise DownloadError(f"未能解析到有效直链 [{remote_path}]")

        # 合并 path 与 server_filename
        meta["path"] = remote_path
        meta["server_filename"] = info.get("server_filename", os.path.basename(remote_path))
        return meta

    def download_file(
        self,
        remote_path: str,
        local_dest: str | Path,
        overwrite: bool = False,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        """下载网盘文件至本地，支持断点续传与 User-Agent 防盗链穿透。

        Args:
            remote_path: 网盘文件路径。
            local_dest: 本地目标文件路径或目标目录。
            overwrite: 若本地目标已存在是否覆盖。
            progress: 进度回调函数，接收 phase, downloaded, total, speed 等事件。

        Returns:
            本地最终完整文件路径。
        """
        meta = self.get_dlink(remote_path)
        dlink = meta["dlink"]
        total_size = meta.get("size", 0)
        filename = meta.get("server_filename") or os.path.basename(remote_path)

        local_dest_path = Path(local_dest).resolve()
        if local_dest_path.is_dir():
            target_file = local_dest_path / filename
        else:
            target_file = local_dest_path

        if target_file.exists() and not overwrite:
            if target_file.stat().st_size == total_size:
                logger.info("本地已存在同名且大小一致的文件，跳过下载: %s", target_file)
                return str(target_file)
            raise DownloadError(f"本地文件已存在且未开启 overwrite: {target_file}")

        target_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = target_file.with_name(target_file.name + ".tmp")

        # 断点续传检查
        current_size = tmp_file.stat().st_size if tmp_file.exists() else 0
        if current_size > total_size:
            # 临时文件损坏，重新开始
            current_size = 0
            tmp_file.unlink(missing_ok=True)

        req = urllib.request.Request(dlink)
        req.add_header("User-Agent", BAIDU_PAN_UA)
        if current_size > 0:
            req.add_header("Range", f"bytes={current_size}-")

        mode = "ab" if current_size > 0 else "wb"
        downloaded = current_size
        start_time = time.time()
        last_report_time = start_time

        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_file, mode) as f:
                while True:
                    buf = resp.read(CHUNK_READ_SIZE)
                    if not buf:
                        break
                    f.write(buf)
                    downloaded += len(buf)

                    now = time.time()
                    if progress and (now - last_report_time >= 0.5 or downloaded == total_size):
                        elapsed = now - start_time
                        speed = (downloaded - current_size) / elapsed if elapsed > 0 else 0
                        progress({
                            "phase": "download",
                            "downloaded": downloaded,
                            "total": total_size,
                            "speed": speed,
                            "filename": filename,
                        })
                        last_report_time = now
        except Exception as e:
            raise DownloadError(f"下载传输异常 [{remote_path}]: {e}") from e

        # 校验下载完整性
        if total_size > 0 and downloaded < total_size:
            raise DownloadError(f"下载不完整 [{downloaded}/{total_size} 字节]，已保留临时文件供续传: {tmp_file}")

        # 原子重命名为正式文件
        tmp_file.replace(target_file)
        return str(target_file)

    @staticmethod
    def generate_export_command(dlink: str, filename: str, style: str = "aria2") -> str:
        """生成便于外部工具（aria2c 或 curl）高速下载的命令。"""
        if style.lower() == "curl":
            return f'curl -C - -H "User-Agent: {BAIDU_PAN_UA}" -o "{filename}" "{dlink}"'
        # 默认 aria2
        return (
            f'aria2c -c -s16 -x16 --header="User-Agent: {BAIDU_PAN_UA}" '
            f'"{dlink}" -o "{filename}"'
        )
