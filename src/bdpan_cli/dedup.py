"""网盘冲突副本与重复文件扫描与治理模块 (BK-0027)。

支持检测并治理百度网盘因重复上传或同步产生的形如 `(1)`、`(2)` 的冲突副本、
无主编号副本以及空目录，提供安全隔离（--staging-dir）与回收站清理（--delete）。
"""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from bdpan_cli.file_manager import FileManager, FileManagerError

logger = logging.getLogger(__name__)

# 匹配冲突副本后缀，如 "name (1)", "name(2)", "name (01).mp4", "name (1).mkv"
# index 限制为 1-3 位数字，自动排除 4 位年份数字如 (1995), (2021)
CONFLICT_SUFFIX_PATTERN = re.compile(
    r"^(?P<base>.+?)(?:[\s._-]*)?\((?P<index>\d{1,3})\)(?P<ext>\.[^.]+)?$"
)


@dataclass
class DedupCandidate:
    """待治理的冲突副本或重复项。"""

    path: str
    name: str
    isdir: bool
    size: int
    reason: str
    clean_name: str
    primary_path: str | None = None


@dataclass
class DedupPlan:
    """重复项治理扫描计划与统计。"""

    target_dir: str
    candidates: list[DedupCandidate]
    total_size: int
    scanned_count: int
    orphan_groups_count: int = 0


def scan_directory_duplicates(
    dir_path: str,
    entries: list[dict[str, Any]],
    include_orphans: bool = False,
    include_empty: bool = False,
    mgr: FileManager | None = None,
) -> tuple[list[DedupCandidate], int]:
    """在单层目录条目中检测冲突副本与重复项。

    Args:
        dir_path: 当前扫描的父目录绝对路径。
        entries: 当前目录下的条目列表（来自 list_dir 或 walk 分组）。
        include_orphans: 是否将无主冲突副本组（如缺少未带编号原版但有 (1)/(2)）中更高编号项视为冗余。
        include_empty: 是否检测并标记空子目录。
        mgr: 可选的 FileManager 实例，用于单层模式下探查子目录是否为空。

    Returns:
        (candidates, orphan_groups_count) 二元组。
    """
    entry_map: dict[str, dict[str, Any]] = {
        e.get("server_filename", ""): e for e in entries if e.get("server_filename")
    }
    candidates: list[DedupCandidate] = []
    orphan_groups: dict[tuple[str, str, bool], list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    for e in entries:
        fname = e.get("server_filename", "")
        if not fname:
            continue
        isdir = e.get("isdir") == 1
        path = e.get("path") or f"{dir_path.rstrip('/')}/{fname}"
        size = int(e.get("size") or 0)

        # 1. 检测空目录（若启用）
        if include_empty and isdir:
            is_empty = False
            if mgr is not None:
                try:
                    sub_entries = mgr.list_dir(path, limit=1)
                    if len(sub_entries) == 0:
                        is_empty = True
                except Exception as ex:
                    logger.debug("探查目录是否为空失败 [%s]: %s", path, ex)
            if is_empty:
                candidates.append(
                    DedupCandidate(
                        path=path,
                        name=fname,
                        isdir=True,
                        size=0,
                        reason="空目录 (0 项)",
                        clean_name=fname,
                    )
                )
                continue

        # 2. 匹配冲突副本正则 (1), (2) ...
        m = CONFLICT_SUFFIX_PATTERN.match(fname)
        if not m:
            continue

        base = m.group("base").rstrip(" ._-")
        idx = int(m.group("index"))
        ext = m.group("ext") or ""
        clean_name = f"{base}{ext}" if not isdir else base

        # 检查同目录下是否存在未带序号的主条目
        if clean_name in entry_map and entry_map[clean_name].get("isdir") == e.get("isdir"):
            primary = entry_map[clean_name]
            if not isdir:
                if size == int(primary.get("size") or 0):
                    reason = f"存在同名主文件 '{clean_name}' 且大小一致 ({idx})"
                else:
                    reason = f"存在同名主文件 '{clean_name}' (序号冲突副本 ({idx}))"
            else:
                reason = f"存在同名主目录 '{clean_name}' (冲突副本 ({idx}))"

            candidates.append(
                DedupCandidate(
                    path=path,
                    name=fname,
                    isdir=isdir,
                    size=size,
                    reason=reason,
                    clean_name=clean_name,
                    primary_path=primary.get("path"),
                )
            )
        else:
            orphan_groups[(base, ext, isdir)].append((idx, e))

    # 3. 处理无主冲突副本组
    orphan_groups_count = 0
    for (base, ext, isdir), group in orphan_groups.items():
        if len(group) > 1:
            orphan_groups_count += 1
            if include_orphans:
                # 排序保留序号最小者，更高序号作为冗余候选
                sorted_group = sorted(group, key=lambda x: x[0])
                kept_idx, kept_entry = sorted_group[0]
                kept_name = kept_entry.get("server_filename", "")
                clean_name = f"{base}{ext}" if not isdir else base
                for idx, item in sorted_group[1:]:
                    item_path = item.get("path") or f"{dir_path.rstrip('/')}/{item.get('server_filename')}"
                    item_name = item.get("server_filename", "")
                    candidates.append(
                        DedupCandidate(
                            path=item_path,
                            name=item_name,
                            isdir=isdir,
                            size=int(item.get("size") or 0),
                            reason=f"无主条目，同组保留最低序号 '{kept_name}' (冗余副本 ({idx}))",
                            clean_name=clean_name,
                            primary_path=kept_entry.get("path"),
                        )
                    )

    return candidates, orphan_groups_count


def plan_dedup(
    dir_path: str,
    mgr: FileManager,
    recursive: bool = False,
    include_orphans: bool = False,
    include_empty: bool = False,
) -> DedupPlan:
    """扫描指定网盘目录并规划冲突副本治理方案。

    Args:
        dir_path: 网盘目标目录。
        mgr: FileManager 实例。
        recursive: 是否递归扫描所有子目录。
        include_orphans: 是否处理无主冲突副本组（保留 (1)，清理 (2)+）。
        include_empty: 是否清理空目录。

    Returns:
        DedupPlan 规划结果对象。
    """
    clean_dir = "/" + dir_path.strip("/") if dir_path != "/" else "/"
    logger.info("开始扫描冲突副本: target=%s, recursive=%s", clean_dir, recursive)

    if not recursive:
        entries = mgr.list_dir(clean_dir)
        candidates, orphan_count = scan_directory_duplicates(
            clean_dir,
            entries,
            include_orphans=include_orphans,
            include_empty=include_empty,
            mgr=mgr,
        )
        total_size = sum(c.size for c in candidates)
        return DedupPlan(
            target_dir=clean_dir,
            candidates=candidates,
            total_size=total_size,
            scanned_count=len(entries),
            orphan_groups_count=orphan_count,
        )

    # 递归模式：通过 DFS walk 遍历全子树并按父目录分组治理
    entries, errors = mgr.walk(clean_dir)
    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_dir_paths: set[str] = set()

    for _, entry in entries:
        p = entry.get("path", "")
        if entry.get("isdir") == 1:
            all_dir_paths.add(p)
        parent = os.path.dirname(p) or "/"
        by_parent[parent].append(entry)

    all_candidates: list[DedupCandidate] = []
    total_orphan_count = 0

    # 逐目录检测冲突副本
    for parent_dir, dir_entries in by_parent.items():
        cand, orph = scan_directory_duplicates(
            parent_dir,
            dir_entries,
            include_orphans=include_orphans,
            include_empty=False,  # 递归模式下空目录统一在下方处理
            mgr=None,
        )
        all_candidates.extend(cand)
        total_orphan_count += orph

    # 递归模式检测空目录（若开启）
    if include_empty:
        non_empty_parents = set(by_parent.keys())
        for dpath in all_dir_paths:
            # 若一个目录不在任何条目的父目录集合中，且自身不是由已标记候选构成的
            if dpath not in non_empty_parents:
                dname = os.path.basename(dpath)
                all_candidates.append(
                    DedupCandidate(
                        path=dpath,
                        name=dname,
                        isdir=True,
                        size=0,
                        reason="空目录 (0 项)",
                        clean_name=dname,
                    )
                )

    total_size = sum(c.size for c in all_candidates)
    return DedupPlan(
        target_dir=clean_dir,
        candidates=all_candidates,
        total_size=total_size,
        scanned_count=len(entries),
        orphan_groups_count=total_orphan_count,
    )


def execute_dedup(
    plan: DedupPlan,
    mgr: FileManager,
    staging_dir: str | None = None,
    delete: bool = False,
    batch_size: int = 50,
) -> dict[str, int]:
    """执行重复项治理计划（移动到暂存目录或直接删除）。

    Args:
        plan: 治理计划。
        mgr: FileManager 实例。
        staging_dir: 隔离暂存目录路径（若指定则批量移动至该目录）。
        delete: 若为 True 则直接移入网盘回收站。
        batch_size: 每批次提交上限（默认 50）。

    Returns:
        包含 'moved' 和 'deleted' 数量的字典。
    """
    if not plan.candidates:
        return {"moved": 0, "deleted": 0}

    if staging_dir:
        clean_staging = "/" + staging_dir.strip("/")
        # 确保隔离目录存在
        try:
            mgr.mkdir(clean_staging)
        except FileManagerError:
            pass

        items_to_move = [
            (c.path, clean_staging, c.name)
            for c in plan.candidates
        ]
        logger.info("正在批量移动 %d 个冲突副本至 %s", len(items_to_move), clean_staging)
        mgr.batch_move(items_to_move, batch_size=batch_size)
        return {"moved": len(items_to_move), "deleted": 0}

    if delete:
        paths_to_delete = [c.path for c in plan.candidates]
        logger.info("正在批量删除 %d 个冲突副本入回收站", len(paths_to_delete))
        mgr.batch_delete(paths_to_delete, batch_size=batch_size)
        return {"moved": 0, "deleted": len(paths_to_delete)}

    return {"moved": 0, "deleted": 0}
