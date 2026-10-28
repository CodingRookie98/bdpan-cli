"""文件上传客户端：预上传 → 分片上传 → 创建文件，支持断点续传。

三阶段规格依据官方文档（更新时间以 openapi 文档站为准）：
- 预上传 precreate：autoinit 固定为 1，block_list 为各分片 MD5（32 位小写）
  JSON 数组；响应 block_list 为**需要上传的分片序号列表**（从 0 起）。
- 分片上传 superfile2：type 固定为 "tmpfile"，partseq 从 0 起；非末片必须
  足 4MB（errno=31299），普通用户单文件上限 4GB。
- 创建文件 create：path/size/isdir/block_list/uploadid/rtype 须与预上传
  完全一致；rtype 0 冲突失败 / 1 冲突重命名 / 3 覆盖。

断点续传说明（2026-10-07 真网盘实测）：服务端**不按路径跨任务记忆分片**，
换新 uploadid 重新预上传后缺片列表仍为全量；分片记忆绑定在 uploadid 上。
故续传采用本地状态文件（记录 uploadid + 已成功分片），恢复时凭原 uploadid
仅补传缺失分片；uploadid 失效或服务端校验不过时自动回退全新上传。
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from bdpan_cli._vendor import openapi_client
from bdpan_cli._vendor.openapi_client.api.fileupload_api import FileuploadApi
from bdpan_cli._vendor.openapi_client.rest import ApiException

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4 * 1024 * 1024  # 官方分片基准 4MB（普通用户非末片必须足 4MB）
_CHUNK_RETRY = 3  # 分片上传瞬时失败重试次数


class UploadError(RuntimeError):
    """上传流程异常。"""


class _NamedBytesIO(io.BytesIO):
    """SDK 多部件序列化要求文件对象带 .name 属性（取文件名与 MIME 推断）。"""

    name = "blob"


class Uploader:
    """网盘文件上传封装（三阶段，本地状态文件断点续传）。"""

    def __init__(self, access_token: str, api_client: openapi_client.ApiClient | None = None) -> None:
        self.access_token = access_token
        self.api_client = api_client or openapi_client.ApiClient()
        self._fileupload_api = FileuploadApi(self.api_client)

    def locate_upload_host(self) -> str:
        """动态探测最优机房上传 host，失败时回退至默认 d.pcs.baidu.com。"""
        url = f"https://d.pcs.baidu.com/rest/2.0/pcs/file?method=locateupload&access_token={self.access_token}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pan.baidu.com"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                servers = data.get("servers") or []
                if servers and isinstance(servers, list):
                    host = servers[0].get("host")
                    if host:
                        return str(host)
        except Exception as e:
            logger.debug("动态机房探测失败，使用默认 host: %s", e)
        return "d.pcs.baidu.com"

    # ------------------------------------------------------------------
    # 分片规划与哈希
    # ------------------------------------------------------------------

    @staticmethod
    def _plan_chunks(size: int, chunk_size: int = CHUNK_SIZE) -> list[tuple[int, int]]:
        """规划分片: 返回 (offset, length) 列表；≤chunk_size 单片。"""
        if size <= chunk_size:
            return [(0, size)]
        return [(i, min(chunk_size, size - i)) for i in range(0, size, chunk_size)]

    @staticmethod
    def _hash_file(local_path: str, chunks: list[tuple[int, int]]) -> list[str]:
        """逐片流式计算内容 MD5（32 位小写），不整读大文件进内存。"""
        md5s: list[str] = []
        with open(local_path, "rb") as f:
            for offset, length in chunks:
                f.seek(offset)
                h = hashlib.md5()
                remaining = length
                while remaining > 0:
                    buf = f.read(min(1024 * 1024, remaining))
                    if not buf:
                        raise UploadError(f"本地文件读取提前结束 [{local_path}] @{offset}")
                    h.update(buf)
                    remaining -= len(buf)
                md5s.append(h.hexdigest())
        return md5s

    # ------------------------------------------------------------------
    # 三阶段流程
    # ------------------------------------------------------------------

    def upload(
        self,
        local_path: str,
        remote_path: str,
        rtype: int = 1,
        progress: Callable[[dict[str, Any]], None] | None = None,
        state_file: str | Path | None = None,
        local_key: str | None = None,
    ) -> dict[str, Any]:
        """上传本地文件到网盘指定路径。

        Args:
            local_path: 本地文件路径（必须为已存在文件）。
            remote_path: 网盘目标文件绝对路径。
            rtype: 冲突策略，与预上传/创建两阶段保持一致
                （1 冲突重命名，3 覆盖）。
            progress: 进度回调，接收 phase=precreate/resume/chunk/create 事件。
            state_file: 断点续传状态文件路径；None 为不持久化（单次完成，
                中断即从头再来）。
            local_key: 状态键的本地侧标识（默认 local_path），用于同一本地
                文件分批传到多个远端路径时区分任务。

        Returns:
            创建文件阶段的响应（含 path/size/fs_id 等）。
        """
        if not os.path.isfile(local_path):
            raise UploadError(f"本地文件不存在 [{local_path}]")

        key = f"{local_key or local_path}->{remote_path}"
        size = os.path.getsize(local_path)
        chunks = self._plan_chunks(size)
        md5s = self._hash_file(local_path, chunks)

        state = self._load_state(state_file, key) if state_file else None
        if state and state.get("size") == size and state.get("md5s") == md5s:
            try:
                res = self._upload_resume(
                    state, chunks, local_path, remote_path, rtype, md5s, progress
                )
                self._clear_state(state_file, key)
                return res
            except UploadError as e:
                logger.info("续传任务失效，回退全新上传: %s", e)
                self._clear_state(state_file, key)

        return self._upload_fresh(
            local_path, remote_path, size, chunks, md5s, rtype, progress, state_file, key
        )

    def _upload_resume(
        self,
        state: dict[str, Any],
        chunks: list[tuple[int, int]],
        local_path: str,
        remote_path: str,
        rtype: int,
        md5s: list[str],
        progress: Callable[[dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        """凭本地状态（原 uploadid + 已传分片）续传。"""
        uploadid = str(state["uploadid"])
        uploaded: set[int] = set(state.get("uploaded") or [])
        missing = [i for i in range(len(chunks)) if i not in uploaded]
        if progress:
            progress({"phase": "resume", "present": len(uploaded), "missing": len(missing)})
        for seq in missing:
            self._upload_chunk(uploadid, remote_path, seq, chunks, local_path, progress)
        return self._create(remote_path, int(state["size"]), md5s, uploadid, rtype, progress)

    def _upload_fresh(
        self,
        local_path: str,
        remote_path: str,
        size: int,
        chunks: list[tuple[int, int]],
        md5s: list[str],
        rtype: int,
        progress: Callable[[dict[str, Any]], None] | None,
        state_file: str | Path | None,
        key: str,
    ) -> dict[str, Any]:
        """全新三阶段上传；状态文件存在时边传边记账。"""
        pre = self._precreate(remote_path, size, md5s, rtype)
        if progress:
            progress({"phase": "precreate"})
        uploadid = str(pre["uploadid"])

        # 极速秒传判定：云端命中相同特征文件，无需上传任何分片直接创建
        if pre.get("return_type") == 2:
            if progress:
                progress({"phase": "fast_upload", "uploadid": uploadid})
            res = self._create(remote_path, size, md5s, uploadid, rtype, progress)
            self._clear_state(state_file, key)
            return res

        missing = [int(x) for x in pre.get("block_list") or []]
        uploaded = [i for i in range(len(chunks)) if i not in missing]
        self._save_state(
            state_file, key, local_path, remote_path, size, uploadid, md5s, uploaded
        )

        for seq in missing:
            self._upload_chunk(uploadid, remote_path, seq, chunks, local_path, progress)
            uploaded.append(seq)
            self._save_state(
                state_file, key, local_path, remote_path, size, uploadid, md5s, uploaded
            )

        res = self._create(remote_path, size, md5s, uploadid, rtype, progress)
        self._clear_state(state_file, key)
        return res

    # ------------------------------------------------------------------
    # 状态文件（断点续传账本）
    # ------------------------------------------------------------------

    @staticmethod
    def _load_state(state_file: str | Path | None, key: str) -> dict[str, Any] | None:
        if not state_file:
            return None
        try:
            with open(state_file, encoding="utf-8") as f:
                book = json.load(f)
            return book.get(key) if isinstance(book, dict) else None
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("续传状态文件不可读，按全新上传处理 [%s]: %s", state_file, e)
            return None

    @staticmethod
    def _save_state(
        state_file: str | Path | None,
        key: str,
        local_path: str,
        remote_path: str,
        size: int,
        uploadid: str,
        md5s: list[str],
        uploaded: list[int],
    ) -> None:
        if not state_file:
            return
        book: dict[str, Any] = {}
        try:
            with open(state_file, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                book = loaded
        except (OSError, json.JSONDecodeError):
            pass
        book[key] = {
            "local_path": local_path,
            "remote_path": remote_path,
            "size": size,
            "uploadid": uploadid,
            "md5s": md5s,
            "uploaded": uploaded,
            "updated_at": int(time.time()),
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(book, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _clear_state(state_file: str | Path | None, key: str) -> None:
        if not state_file:
            return
        try:
            with open(state_file, encoding="utf-8") as f:
                book = json.load(f)
            if isinstance(book, dict) and book.pop(key, None) is not None:
                if book:
                    with open(state_file, "w", encoding="utf-8") as f:
                        json.dump(book, f, ensure_ascii=False, indent=2)
                else:
                    os.unlink(state_file)
        except (OSError, json.JSONDecodeError):
            pass

    # ------------------------------------------------------------------
    # 三阶段原语
    # ------------------------------------------------------------------

    def _precreate(
        self,
        remote_path: str,
        size: int,
        md5s: list[str],
        rtype: int,
    ) -> dict[str, Any]:
        block_list = json.dumps(md5s, separators=(",", ":"))
        try:
            res = self._fileupload_api.xpanfileprecreate(
                access_token=self.access_token,
                path=remote_path,
                isdir=0,
                size=size,
                autoinit=1,
                block_list=block_list,
                rtype=rtype,
            )
        except ApiException as e:
            raise UploadError(f"预上传失败 [{remote_path}]: {e.status} {e.body}") from e
        return self._check(res, f"预上传返回错误 [{remote_path}]")

    def _upload_chunk(
        self,
        uploadid: str,
        remote_path: str,
        seq: int,
        chunks: list[tuple[int, int]],
        local_path: str,
        progress: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        offset, length = chunks[seq]
        with open(local_path, "rb") as f:
            f.seek(offset)
            data = f.read(length)
        if len(data) != length:
            raise UploadError(f"本地文件读取提前结束 [{local_path}] @{offset}")

        last_error: Exception | None = None
        for attempt in range(1, _CHUNK_RETRY + 1):
            try:
                # SDK 的 file 参数要求带 .name 的 IOBase 文件对象
                res = self._fileupload_api.pcssuperfile2(
                    access_token=self.access_token,
                    partseq=str(seq),
                    path=remote_path,
                    uploadid=uploadid,
                    type="tmpfile",
                    file=_NamedBytesIO(data),
                )
                self._check_chunk(res, f"分片上传返回错误 [{remote_path} #{seq}]")
                if progress:
                    progress({"phase": "chunk", "seq": seq, "total": len(chunks)})
                return
            except (ApiException, UploadError) as e:
                last_error = e
                logger.warning("分片 %d 上传第 %d 次尝试失败: %s", seq, attempt, e)
                if attempt < _CHUNK_RETRY:
                    time.sleep(1)
        raise UploadError(f"分片上传失败 [{remote_path} #{seq}] 重试 {_CHUNK_RETRY} 次后放弃: {last_error}") from last_error

    def _create(
        self,
        remote_path: str,
        size: int,
        md5s: list[str],
        uploadid: str,
        rtype: int,
        progress: Callable[[dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        block_list = json.dumps(md5s, separators=(",", ":"))
        try:
            res = self._fileupload_api.xpanfilecreate(
                access_token=self.access_token,
                path=remote_path,
                isdir=0,
                size=size,
                uploadid=uploadid,
                block_list=block_list,
                rtype=rtype,
            )
        except ApiException as e:
            raise UploadError(f"创建文件失败 [{remote_path}]: {e.status} {e.body}") from e
        if progress:
            progress({"phase": "create"})
        return self._check(res, f"创建文件返回错误 [{remote_path}]")

    @staticmethod
    def _check(res: Any, ctx: str) -> dict[str, Any]:
        if not isinstance(res, dict) or res.get("errno") != 0:
            detail = res if isinstance(res, dict) else repr(res)
            errno = res.get("errno") if isinstance(res, dict) else "?"
            raise UploadError(f"{ctx}: errno={errno} ({detail})")
        return res

    @staticmethod
    def _check_chunk(res: Any, ctx: str) -> dict[str, Any]:
        """分片上传响应校验。

        官方规格：成功响应仅含 md5/request_id，errno 字段失败时才返回，
        故"无 errno"视作成功（区别于预上传/创建恒带 errno 的形态）。
        """
        if isinstance(res, dict) and res.get("errno") not in (0, None):
            raise UploadError(f"{ctx}: errno={res.get('errno')} ({res})")
        return res
