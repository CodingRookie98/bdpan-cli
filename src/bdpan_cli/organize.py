"""电影目录规整与迁移任务脚本。"""

from __future__ import annotations

import logging
import sys
from typing import Any

from bdpan_cli.auth import TokenManager
from bdpan_cli.config import load_config
from bdpan_cli.file_manager import FileManager

logger = logging.getLogger(__name__)

ROOT_DIR = "/影视/电影"
UNWATCHED_OLD = f"{ROOT_DIR}/0_notWatch"
UNWATCHED_NEW_NAME = "unwatched"
UNWATCHED_NEW_PATH = f"{ROOT_DIR}/{UNWATCHED_NEW_NAME}"
WATCHED_DIR = f"{ROOT_DIR}/watched"
TRIAGE_DIR = f"{ROOT_DIR}/pending_triage"


def run_organization() -> None:
    config = load_config()
    token = TokenManager(config).get_access_token()
    mgr = FileManager(token)

    logger.info("=== 阶段 0: 检查当前目录状态 ===")
    entries = mgr.list_dir(ROOT_DIR, limit=1000)
    name_map = {e.get("server_filename"): e for e in entries}
    logger.info("当前 %s 下共有 %d 个条目", ROOT_DIR, len(entries))

    # 1. 待看目录重命名
    logger.info("=== 阶段 1: 重命名待看目录 ===")
    if "0_notWatch" in name_map:
        logger.info("发现 0_notWatch，开始重命名为 %s ...", UNWATCHED_NEW_NAME)
        res_rename = mgr.rename(UNWATCHED_OLD, UNWATCHED_NEW_NAME)
        logger.info("重命名成功: %s", res_rename)
    elif UNWATCHED_NEW_NAME in name_map:
        logger.info("目录 %s 已存在，跳过重命名", UNWATCHED_NEW_NAME)
    else:
        logger.warning("未找到 0_notWatch 或 %s，请确认目录状态", UNWATCHED_NEW_NAME)

    # 2. 创建目标目录
    logger.info("=== 阶段 2: 确保目标目录存在 ===")
    logger.info("创建/确保已看目录: %s", WATCHED_DIR)
    mgr.mkdir(WATCHED_DIR)
    logger.info("创建/确保待整理目录: %s", TRIAGE_DIR)
    mgr.mkdir(TRIAGE_DIR)

    # 3. 重新扫描根目录以获取最新条目清单
    logger.info("=== 阶段 3: 扫描待归类文件与目录 ===")
    current_entries = mgr.list_dir(ROOT_DIR, limit=1000)

    # 保留在根目录的三个核心文件夹
    preserved_names = {UNWATCHED_NEW_NAME, "0_notWatch", "watched", "pending_triage"}

    items_to_triage: list[tuple[str, str, str]] = []  # (src_path, dest_dir, new_name)
    items_to_watched: list[tuple[str, str, str]] = []

    for item in current_entries:
        fname = item.get("server_filename")
        if fname in preserved_names:
            continue
        fpath = item.get("path")
        isdir = item.get("isdir") == 1

        if isdir:
            items_to_watched.append((fpath, WATCHED_DIR, fname))
        else:
            # 种子、压缩包、单视频、字幕等全部非目录文件移至 pending_triage
            items_to_triage.append((fpath, TRIAGE_DIR, fname))

    logger.info("待迁移到 watched (电影目录): %d 项", len(items_to_watched))
    logger.info("待迁移到 pending_triage (杂项文件): %d 项", len(items_to_triage))

    # 4. 执行迁移到 pending_triage
    if items_to_triage:
        logger.info("开始分批迁移杂项文件到 %s (批次大小 50)...", TRIAGE_DIR)
        res_triage = mgr.batch_move(items_to_triage, batch_size=50)
        logger.info("杂项文件迁移完成，共调用 %d 个批次", len(res_triage))

    # 5. 执行迁移到 watched
    if items_to_watched:
        logger.info("开始分批迁移电影目录到 %s (批次大小 50)...", WATCHED_DIR)
        res_watched = mgr.batch_move(items_to_watched, batch_size=50)
        logger.info("电影目录迁移完成，共调用 %d 个批次", len(res_watched))

    # 6. 对账与最终验证
    logger.info("=== 阶段 4: 迁移后对账审计 ===")
    final_root_entries = mgr.list_dir(ROOT_DIR, limit=1000)
    root_names = [e.get("server_filename") for e in final_root_entries]
    logger.info("%s 根目录最终条目数: %d -> %s", ROOT_DIR, len(root_names), root_names)

    watched_entries = mgr.list_dir(WATCHED_DIR, limit=1000)
    logger.info("%s 下最终条目数: %d", WATCHED_DIR, len(watched_entries))

    triage_entries = mgr.list_dir(TRIAGE_DIR, limit=1000)
    logger.info("%s 下最终条目数: %d", TRIAGE_DIR, len(triage_entries))

    unwatched_entries = mgr.list_dir(UNWATCHED_NEW_PATH, limit=1000)
    logger.info("%s 下最终条目数: %d", UNWATCHED_NEW_PATH, len(unwatched_entries))

    logger.info("=== 迁移完成！ ===")


if __name__ == "__main__":
    run_organization()
