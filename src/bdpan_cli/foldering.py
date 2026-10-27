"""散落电影/视频/压缩包文件自动规整：识别并创建方案 A 规范目录并将文件移入。"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from bdpan_cli.file_manager import FileManager
from bdpan_cli.preview_scrape import is_already_conforming
from bdpan_cli.scraper import MovieScraper

logger = logging.getLogger(__name__)

MEDIA_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".ts",
    ".iso",
    ".zip",
    ".7z",
    ".rar",
}

SUBTITLE_EXTENSIONS = {
    ".srt",
    ".ass",
    ".sub",
    ".vtt",
}

ALLOWED_EXTENSIONS = MEDIA_EXTENSIONS | SUBTITLE_EXTENSIONS


def plan_foldering(
    dir_path: str,
    mgr: FileManager,
    scraper: MovieScraper | None = None,
) -> list[dict[str, Any]]:
    """扫描目标目录下散落的音视频、字幕与非规范子目录，生成方案 A 规范目录归集计划。

    返回列表中的每一项表示一个待创建的独立电影目录及归入其中的文件清单。
    """
    if scraper is None:
        scraper = MovieScraper()

    logger.info("正在扫描目录 %s 中的待整理媒体与子目录...", dir_path)
    entries = mgr.list_dir(dir_path)

    # 1. 过滤散落媒体文件与非规范子目录
    media_groups: list[dict[str, Any]] = []
    for item in entries:
        if item.get("isdir") == 1:
            subdir_name = item.get("server_filename", "")
            # 若子目录已经严格符合方案 A 规范，跳过不处理
            if is_already_conforming(subdir_name):
                continue
            # 否则扫描非规范子目录内部的媒体文件与字幕
            sub_path = item.get("path", f"{dir_path}/{subdir_name}")
            try:
                sub_entries = mgr.list_dir(sub_path)
            except Exception as e:
                logger.warning("扫描子目录失败 [%s]: %s", subdir_name, e)
                continue

            sub_media = []
            for sub_item in sub_entries:
                if sub_item.get("isdir") == 1:
                    continue
                sfname = sub_item.get("server_filename", "")
                _, sext = os.path.splitext(sfname)
                if sext.lower() in ALLOWED_EXTENSIONS:
                    sub_media.append(sub_item)

            if sub_media:
                media_groups.append({
                    "query_name": subdir_name,
                    "files": sub_media,
                    "source_dir": sub_path,
                })
        else:
            fname = item.get("server_filename", "")
            _, ext = os.path.splitext(fname)
            if ext.lower() in ALLOWED_EXTENSIONS:
                base_name, _ = os.path.splitext(fname)
                media_groups.append({
                    "query_name": base_name,
                    "files": [item],
                    "source_dir": None,
                })

    logger.info("共发现 %d 组待整理媒体项", len(media_groups))

    # 2. 逐一识别并匹配方案 A 规范目录名
    folder_groups: dict[str, list[dict[str, Any]]] = {}

    for group in media_groups:
        query_name = group["query_name"]
        base_name, _ = os.path.splitext(query_name)
        is_trailer = bool(re.search(r"Theatrical\s*Trailer|Trailer|预告片?", base_name, re.IGNORECASE))
        query = base_name
        if is_trailer:
            query = re.sub(r"Theatrical\s*Trailer|Trailer|预告片?", " ", query, flags=re.IGNORECASE).strip()

        # 特殊情况消歧：例如张艺谋《狙击手》无年份标注但打包于2022
        if "狙击手" in query and not re.search(r"\b(19\d{2}|20\d{2})\b", query):
            query = f"{query} 2022"

        meta = scraper.scrape_folder_name(query)
        if meta and meta.formatted_name:
            target_name = meta.formatted_name
            # 净化中英文标点与逗号
            target_name = re.sub(r"[\/\\:\*\?\"<>\|\s_,]+", ".", target_name.strip())
            target_name = re.sub(r"\.{2,}", ".", target_name).strip(".")
            if is_trailer and not target_name.endswith(".Trailer"):
                target_name = f"{target_name}.Trailer"
        else:
            # 无法识别时回退为原文件名（去除扩展名）
            target_name = base_name.strip(".")

        if target_name not in folder_groups:
            folder_groups[target_name] = []

        for f_item in group["files"]:
            fname = f_item.get("server_filename", "")
            fpath = f_item.get("path", f"{dir_path}/{fname}")
            folder_groups[target_name].append({
                "filename": fname,
                "path": fpath,
                "size": f_item.get("size", 0),
                "is_trailer": is_trailer,
            })

    # 3. 组织为计划清单
    plan: list[dict[str, Any]] = []
    for folder_name, files in folder_groups.items():
        plan.append({
            "target_folder_name": folder_name,
            "target_folder_path": f"{dir_path}/{folder_name}",
            "files": files,
        })

    return plan


def execute_foldering(
    dir_path: str,
    plan: list[dict[str, Any]],
    mgr: FileManager,
    batch_size: int = 25,
) -> dict[str, int]:
    """依据整理计划执行目录创建与文件原子移动。"""
    created_count = 0
    items_to_move: list[tuple[str, str, str]] = []

    # 1. 批量创建目标方案 A 电影目录
    for group in plan:
        target_dir = group["target_folder_path"]
        logger.info("创建电影规范目录: %s", target_dir)
        mgr.mkdir(target_dir)
        created_count += 1

        for f in group["files"]:
            items_to_move.append((f["path"], target_dir, f["filename"]))

    # 2. 批量将散落文件移入对应的电影目录
    logger.info("正在批量移动 %d 个文件至对应规范电影目录...", len(items_to_move))
    mgr.batch_move(items_to_move, batch_size=batch_size)

    logger.info("完成规整！共创建 %d 个目录，移动 %d 个文件", created_count, len(items_to_move))
    return {
        "folders_created": created_count,
        "files_moved": len(items_to_move),
    }
