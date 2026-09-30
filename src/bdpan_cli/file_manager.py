"""文件与目录管理客户端，封装创建、重命名、移动等能力。"""

from __future__ import annotations

import json
import logging
from typing import Any

import openapi_client
from openapi_client.api.fileinfo_api import FileinfoApi
from openapi_client.api.filemanager_api import FilemanagerApi
from openapi_client.api.fileupload_api import FileuploadApi
from openapi_client.rest import ApiException

logger = logging.getLogger(__name__)


class FileManagerError(RuntimeError):
    """文件管理异常基类。"""


class FileManager:
    """网盘文件与目录管理封装。"""

    def __init__(self, access_token: str, api_client: openapi_client.ApiClient | None = None) -> None:
        self.access_token = access_token
        self.api_client = api_client or openapi_client.ApiClient()
        self._fileinfo_api = FileinfoApi(self.api_client)
        self._filemanager_api = FilemanagerApi(self.api_client)
        self._fileupload_api = FileuploadApi(self.api_client)

    def list_dir(self, dir_path: str, limit: int = 1000) -> list[dict[str, Any]]:
        """全量列出指定目录下的条目。"""
        all_entries: list[dict[str, Any]] = []
        start = 0
        page_size = min(limit, 1000)
        while True:
            try:
                res = self._fileinfo_api.xpanfilelist(
                    access_token=self.access_token,
                    dir=dir_path,
                    start=str(start),
                    limit=page_size,
                    web="1",
                    order="name",
                )
            except ApiException as e:
                raise FileManagerError(f"读取目录失败 [{dir_path}]: {e.status} {e.body}") from e

            entries = res.get("list", [])
            if not entries:
                break
            all_entries.extend(entries)
            if len(entries) < page_size:
                break
            start += len(entries)
        return all_entries

    def mkdir(self, path: str) -> dict[str, Any]:
        """创建目录。若目录已存在，视作正常成功。"""
        try:
            res = self._fileupload_api.xpanfilecreate(
                access_token=self.access_token,
                path=path,
                isdir=1,
                size=0,
                uploadid="",
                block_list="[]",
                rtype=1,
            )
            # errno=-8 代表文件/目录已存在
            if isinstance(res, dict) and res.get("errno") not in (0, -8, None):
                raise FileManagerError(f"创建目录服务端返回异常 [{path}]: {res}")
            return res if isinstance(res, dict) else {}
        except ApiException as e:
            raise FileManagerError(f"创建目录失败 [{path}]: {e.status} {e.body}") from e

    def rename(self, path: str, new_name: str) -> dict[str, Any]:
        """重命名单个文件或目录。"""
        filelist = json.dumps([{"path": path, "newname": new_name}], ensure_ascii=False)
        try:
            res = self._filemanager_api.filemanagerrename(
                access_token=self.access_token,
                _async=0,
                filelist=filelist,
            )
        except ApiException as e:
            raise FileManagerError(f"重命名失败 [{path} -> {new_name}]: {e.status} {e.body}") from e

        if not isinstance(res, dict) or res.get("errno") != 0:
            raise FileManagerError(f"重命名返回错误 [{path} -> {new_name}]: {res}")
        return res

    def batch_rename(
        self,
        items: list[tuple[str, str]],
        batch_size: int = 50,
    ) -> list[dict[str, Any]]:
        """批量重命名文件或目录。

        Args:
            items: 包含 (src_path, new_name) 的元组列表。
            batch_size: 每批请求的最大数量（默认 50）。

        Returns:
            各批次成功结果列表。
        """
        results: list[dict[str, Any]] = []
        for i in range(0, len(items), batch_size):
            chunk = items[i : i + batch_size]
            payload = [{"path": src, "newname": newname} for src, newname in chunk]
            filelist = json.dumps(payload, ensure_ascii=False)
            try:
                res = self._filemanager_api.filemanagerrename(
                    access_token=self.access_token,
                    _async=0,
                    filelist=filelist,
                )
            except ApiException as e:
                raise FileManagerError(f"批量重命名批次 {i // batch_size + 1} 失败: {e.status} {e.body}") from e

            if not isinstance(res, dict) or res.get("errno") != 0:
                raise FileManagerError(f"批量重命名批次 {i // batch_size + 1} 返回错误: {res}")
            results.append(res)
        return results


    def batch_move(
        self,
        items: list[tuple[str, str, str]],
        batch_size: int = 50,
    ) -> list[dict[str, Any]]:
        """批量移动文件或目录。

        Args:
            items: 包含 (src_path, dest_dir, new_name) 的元组列表。
            batch_size: 每批请求的最大数量（默认 50，避免接口超时或截断）。

        Returns:
            各批次成功结果列表。
        """
        results: list[dict[str, Any]] = []
        for i in range(0, len(items), batch_size):
            chunk = items[i : i + batch_size]
            payload = [
                {"path": src, "dest": dest, "newname": name}
                for src, dest, name in chunk
            ]
            filelist = json.dumps(payload, ensure_ascii=False)
            try:
                res = self._filemanager_api.filemanagermove(
                    access_token=self.access_token,
                    _async=0,
                    filelist=filelist,
                )
            except ApiException as e:
                raise FileManagerError(f"批量移动批次 {i // batch_size + 1} 失败: {e.status} {e.body}") from e

            if not isinstance(res, dict) or res.get("errno") != 0:
                raise FileManagerError(f"批量移动批次 {i // batch_size + 1} 返回错误: {res}")
            results.append(res)
        return results

    def copy(self, path: str, dest_dir: str, new_name: str) -> dict[str, Any]:
        """复制单个文件或目录到目标目录。"""
        return self.batch_copy([(path, dest_dir, new_name)])[0]

    def batch_copy(
        self,
        items: list[tuple[str, str, str]],
        batch_size: int = 50,
    ) -> list[dict[str, Any]]:
        """批量复制文件或目录。

        Args:
            items: 包含 (src_path, dest_dir, new_name) 的元组列表。
            batch_size: 每批请求的最大数量（默认 50，避免接口超时或截断）。

        Returns:
            各批次成功结果列表。
        """
        results: list[dict[str, Any]] = []
        for i in range(0, len(items), batch_size):
            chunk = items[i : i + batch_size]
            payload = [
                {"path": src, "dest": dest, "newname": name}
                for src, dest, name in chunk
            ]
            filelist = json.dumps(payload, ensure_ascii=False)
            try:
                res = self._filemanager_api.filemanagercopy(
                    access_token=self.access_token,
                    _async=0,
                    filelist=filelist,
                )
            except ApiException as e:
                raise FileManagerError(f"批量复制批次 {i // batch_size + 1} 失败: {e.status} {e.body}") from e

            if not isinstance(res, dict) or res.get("errno") != 0:
                raise FileManagerError(f"批量复制批次 {i // batch_size + 1} 返回错误: {res}")
            results.append(res)
        return results

    def delete(self, path: str) -> dict[str, Any]:
        """删除单个文件或目录。"""
        filelist = json.dumps([path], ensure_ascii=False)
        try:
            res = self._filemanager_api.filemanagerdelete(
                access_token=self.access_token,
                _async=0,
                filelist=filelist,
            )
        except ApiException as e:
            raise FileManagerError(f"删除失败 [{path}]: {e.status} {e.body}") from e

        if not isinstance(res, dict) or res.get("errno") != 0:
            raise FileManagerError(f"删除返回错误 [{path}]: {res}")
        return res

