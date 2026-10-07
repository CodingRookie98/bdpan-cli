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

WalkResult = tuple[list[tuple[int, dict[str, Any]]], list[tuple[str, str]]]


class FileManagerError(RuntimeError):
    """文件管理异常基类。"""


def _validate_filemanager_result(res: Any, prefix: str) -> dict[str, Any]:
    """统一校验 filemanager 四原语（copy/move/rename/delete）的响应。

    响应形如 ``{"errno": 0, "info": [{"errno": 0, ...}, ...]}``，批量场景下
    存在顶层 errno=0 但个别条目 info[].errno != 0 的部分失败形态，仅校验
    顶层会漏报，故逐项复核；任一非零即抛 FileManagerError。部分响应可能
    无 info 字段或缺省条目 errno，视作通过以免对未记载形态误报。
    """
    if not isinstance(res, dict) or res.get("errno") != 0:
        raise FileManagerError(f"{prefix}: {res}")
    info = res.get("info")
    if isinstance(info, list):
        for idx, item in enumerate(info, 1):
            if isinstance(item, dict) and item.get("errno") not in (0, None):
                raise FileManagerError(f"{prefix}: 第 {idx} 项失败 errno={item['errno']} ({item})")
    return res


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

    def walk(self, root: str, max_depth: int | None = None) -> WalkResult:
        """深度优先递归遍历网盘子树。

        引擎说明：SDK 的 MultimediafileApi.xpanfilelistall 在当前应用权限下
        对所有路径均返回 errno=20020「该路径不在允许的访问范围内」（实测，
        含应用自建目录），故采用已验证可用的 xpanfilelist 客户端侧逐层递归，
        每个子目录一次 API 调用。

        Args:
            root: 遍历起点目录。
            max_depth: 最大遍历深度（root 直接子项为深度 0）；None 为不限。

        Returns:
            (entries, errors) 二元组：
            - entries: (depth, entry) 列表，DFS 先序，depth 相对 root；
            - errors: (path, errmsg) 列表，记录不可读目录；单个子目录
              读取失败不中断遍历（降级可观测），root 失败时 entries 为空。
        """
        entries: list[tuple[int, dict[str, Any]]] = []
        errors: list[tuple[str, str]] = []
        self._walk_recursive(root, 0, max_depth, entries, errors)
        return entries, errors

    def _walk_recursive(
        self,
        path: str,
        depth: int,
        max_depth: int | None,
        entries: list[tuple[int, dict[str, Any]]],
        errors: list[tuple[str, str]],
    ) -> None:
        try:
            children = self.list_dir(path)
        except FileManagerError as e:
            logger.warning("遍历跳过不可读目录 [%s]: %s", path, e)
            errors.append((path, str(e)))
            return
        for entry in children:
            entries.append((depth, entry))
            if entry.get("isdir") == 1 and (max_depth is None or depth + 1 < max_depth):
                self._walk_recursive(entry["path"], depth + 1, max_depth, entries, errors)

    def search(
        self,
        key: str,
        dir_path: str | None = None,
        recursion: bool = True,
        page: int = 1,
        num: int = 100,
    ) -> list[dict[str, Any]]:
        """按关键词搜索网盘文件（单页结果）。

        Args:
            key: 搜索关键词。
            dir_path: 限定搜索目录（None 为全盘）。
            recursion: 是否递归子目录。
            page: 页码（从 1 起）。
            num: 每页条数。

        Returns:
            当前页条目列表，条目字段同 list_dir（fs_id/path/server_filename/size/isdir 等）。
        """
        kwargs: dict[str, Any] = {
            "web": "1",
            "num": str(num),
            "page": str(page),
            "recursion": "1" if recursion else "0",
        }
        if dir_path:
            kwargs["dir"] = dir_path
        try:
            res = self._fileinfo_api.xpanfilesearch(
                access_token=self.access_token,
                key=key,
                **kwargs,
            )
        except ApiException as e:
            raise FileManagerError(f"搜索失败 [{key}]: {e.status} {e.body}") from e
        return res.get("list", []) if isinstance(res, dict) else []

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

        return _validate_filemanager_result(res, f"重命名返回错误 [{path} -> {new_name}]")

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

            _validate_filemanager_result(res, f"批量重命名批次 {i // batch_size + 1} 返回错误")
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

            _validate_filemanager_result(res, f"批量移动批次 {i // batch_size + 1} 返回错误")
            results.append(res)
        return results

    def copy(self, path: str, dest_dir: str, new_name: str) -> dict[str, Any]:
        """复制单个文件或目录到目标目录。

        与 batch_copy 共用同一请求与校验通道，但不经批量入口，错误文案
        按单项语境表述（不出现"批量复制批次 N"字样）。
        """
        payload = [{"path": path, "dest": dest_dir, "newname": new_name}]
        return self._copy_request(
            payload,
            api_ctx=f"复制 [{path} -> {dest_dir}/{new_name}]",
            err_prefix=f"复制返回错误 [{path} -> {dest_dir}/{new_name}]",
        )

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
            res = self._copy_request(
                payload,
                api_ctx=f"批量复制批次 {i // batch_size + 1}",
                err_prefix=f"批量复制批次 {i // batch_size + 1} 返回错误",
            )
            results.append(res)
        return results

    def _copy_request(
        self,
        payload: list[dict[str, str]],
        api_ctx: str,
        err_prefix: str,
    ) -> dict[str, Any]:
        """执行单次 filemanagercopy 请求并统一校验。

        api_ctx 用于 ApiException 文案（"…失败"），err_prefix 用于
        响应校验文案（"…返回错误"），二者分离以保持既有文案逐字不变。
        """
        filelist = json.dumps(payload, ensure_ascii=False)
        try:
            res = self._filemanager_api.filemanagercopy(
                access_token=self.access_token,
                _async=0,
                filelist=filelist,
            )
        except ApiException as e:
            raise FileManagerError(f"{api_ctx}失败: {e.status} {e.body}") from e

        return _validate_filemanager_result(res, err_prefix)

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

        return _validate_filemanager_result(res, f"删除返回错误 [{path}]")

