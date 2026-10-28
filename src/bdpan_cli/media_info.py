"""MediaInfo: 百度网盘视频/媒体深度元数据探测与目录聚合统计。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from bdpan_cli._vendor import openapi_client
from bdpan_cli._vendor.openapi_client.api.multimediafile_api import MultimediafileApi
from bdpan_cli._vendor.openapi_client.rest import ApiException
from bdpan_cli.file_manager import FileManager

logger = logging.getLogger(__name__)

# 常见媒体格式分类表
EXTENSION_CATEGORY_MAP = {
    # 视频
    ".mkv": "video",
    ".mp4": "video",
    ".avi": "video",
    ".mov": "video",
    ".wmv": "video",
    ".flv": "video",
    ".rmvb": "video",
    ".ts": "video",
    ".m2ts": "video",
    ".iso": "video",
    # 字幕
    ".srt": "subtitle",
    ".ass": "subtitle",
    ".sub": "subtitle",
    ".vtt": "subtitle",
    ".idx": "subtitle",
    ".sup": "subtitle",
    # 图片/海报
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".bmp": "image",
    ".gif": "image",
    # 音频
    ".mp3": "audio",
    ".flac": "audio",
    ".wav": "audio",
    ".aac": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
    ".ape": "audio",
    # 压缩包
    ".zip": "archive",
    ".rar": "archive",
    ".7z": "archive",
    ".tar": "archive",
    ".gz": "archive",
    # 文档/NFO
    ".nfo": "doc",
    ".txt": "doc",
    ".pdf": "doc",
}


class MediaInfoError(RuntimeError):
    """媒体元数据解析或统计异常基类。"""


def format_duration(seconds: int | float | None) -> str:
    """将秒数格式化为 HH:MM:SS。"""
    if not seconds or seconds < 0:
        return "00:00:00"
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def normalize_resolution(width: int | None, height: int | None) -> str:
    """归一化视频分辨率描述。"""
    if not width or not height:
        return "未知分辨率"
    w, h = int(width), int(height)
    if w >= 3840 or h >= 2160:
        return f"{w}x{h} (4K UHD)"
    if w >= 2560 or h >= 1440:
        return f"{w}x{h} (2K QHD)"
    if w >= 1920 or h >= 1080:
        return f"{w}x{h} (1080P FHD)"
    if w >= 1280 or h >= 720:
        return f"{w}x{h} (720P HD)"
    return f"{w}x{h}"


def normalize_codec(codec: str | None) -> str:
    """归一化编码名称。"""
    if not codec:
        return "未知编码"
    c = str(codec).strip().lower()
    if c in ("hevc", "h265", "h.265"):
        return "HEVC"
    if c in ("h264", "h.264", "avc"):
        return "H.264"
    if c in ("av01", "av1"):
        return "AV1"
    if c in ("vc1", "vc-1"):
        return "VC-1"
    return codec.upper()


class MediaInfoClient:
    """网盘媒体元数据探测与聚合统计客户端。"""

    def __init__(self, access_token: str, api_client: openapi_client.ApiClient | None = None) -> None:
        self.access_token = access_token
        self.api_client = api_client or openapi_client.ApiClient()
        self._multimedia_api = MultimediafileApi(self.api_client)
        self._file_manager = FileManager(access_token, self.api_client)

    def get_media_info(self, remote_path: str) -> dict[str, Any]:
        """获取单个视频/多媒体文件的深度媒体元数据。

        Args:
            remote_path: 网盘文件路径。

        Returns:
            包含分辨率、时长、编码、音轨、文件大小等元数据的结构化字典。

        Raises:
            MediaInfoError: 当文件不存在、为目录或接口异常时抛出。
        """
        info = self._file_manager.get_file_info(remote_path)
        if not info:
            raise MediaInfoError(f"网盘文件不存在: {remote_path}")
        if info.get("isdir") == 1:
            raise MediaInfoError(f"目标为目录，无法解析媒体深度元数据: {remote_path}")

        fs_id = info["fs_id"]
        try:
            res = self._multimedia_api.xpanmultimediafilemetas(
                access_token=self.access_token,
                fsids=json.dumps([fs_id]),
                extra="1",
                needmedia=1,
            )
        except ApiException as e:
            raise MediaInfoError(f"获取媒体元数据 API 异常 [{remote_path}]: {e.status} {e.body}") from e

        if not isinstance(res, dict) or res.get("errno") != 0:
            raise MediaInfoError(f"获取媒体元数据失败 [{remote_path}]: errno={res.get('errno', '?')}")

        entries = res.get("list") or []
        entry = entries[0] if entries else {}

        # 提取字段
        size = int(entry.get("size") or info.get("size") or 0)
        filename = entry.get("server_filename") or info.get("server_filename") or os.path.basename(remote_path)
        ext = os.path.splitext(filename)[1].lower()
        is_video = EXTENSION_CATEGORY_MAP.get(ext) == "video"

        # 尝试从 media_info 或直接字段提取宽/高/时长/编码
        media_info_block = entry.get("media_info") or {}
        video_track = (media_info_block.get("video") or [{}])[0] if isinstance(media_info_block.get("video"), list) and media_info_block.get("video") else {}

        duration = entry.get("duration") or video_track.get("duration") or 0
        width = entry.get("width") or video_track.get("width")
        height = entry.get("height") or video_track.get("height")
        raw_codec = entry.get("video_codec") or video_track.get("codec")

        audio_tracks = media_info_block.get("audio") or []

        return {
            "path": remote_path,
            "filename": filename,
            "fs_id": fs_id,
            "size": size,
            "md5": entry.get("md5") or info.get("md5"),
            "category": EXTENSION_CATEGORY_MAP.get(ext, "other"),
            "is_video": is_video,
            "duration_seconds": int(duration),
            "duration_formatted": format_duration(duration),
            "width": width,
            "height": height,
            "resolution": normalize_resolution(width, height),
            "video_codec": normalize_codec(raw_codec),
            "audio_tracks_count": len(audio_tracks),
            "audio_tracks": audio_tracks,
            "raw_media_info": media_info_block,
        }

    def get_dir_stats(self, remote_path: str, max_depth: int | None = None) -> dict[str, Any]:
        """递归统计指定目录下的容量、文件数及扩展名与类别分布。

        Args:
            remote_path: 网盘目录绝对路径。
            max_depth: 最大扫描深度。

        Returns:
            统计结果字典。
        """
        raw_path = remote_path or "/"
        target_dir = "/" + raw_path.strip("/") if raw_path != "/" else "/"
        entries, errors = self._file_manager.walk(target_dir, max_depth=max_depth)

        total_files = 0
        total_dirs = 0
        total_size = 0
        by_extension: dict[str, dict[str, int]] = {}
        by_category: dict[str, dict[str, int]] = {
            "video": {"count": 0, "size": 0},
            "subtitle": {"count": 0, "size": 0},
            "image": {"count": 0, "size": 0},
            "audio": {"count": 0, "size": 0},
            "archive": {"count": 0, "size": 0},
            "doc": {"count": 0, "size": 0},
            "other": {"count": 0, "size": 0},
        }

        for _, e in entries:
            if e.get("isdir") == 1:
                total_dirs += 1
            else:
                total_files += 1
                size = int(e.get("size") or 0)
                total_size += size
                fname = e.get("server_filename") or ""
                ext = os.path.splitext(fname)[1].lower() or "(no-ext)"

                if ext not in by_extension:
                    by_extension[ext] = {"count": 0, "size": 0}
                by_extension[ext]["count"] += 1
                by_extension[ext]["size"] += size

                cat = EXTENSION_CATEGORY_MAP.get(ext, "other")
                by_category[cat]["count"] += 1
                by_category[cat]["size"] += size

        # 按大小降序排序扩展名
        sorted_ext = dict(sorted(by_extension.items(), key=lambda item: item[1]["size"], reverse=True))

        return {
            "root": target_dir,
            "max_depth": max_depth,
            "total_files": total_files,
            "total_dirs": total_dirs,
            "total_size": total_size,
            "by_extension": sorted_ext,
            "by_category": by_category,
            "errors": [{"path": p, "error": msg} for p, msg in errors],
        }
