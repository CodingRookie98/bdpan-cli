"""依据审核后的 scrape_preview.json 执行网盘目录批量重命名。"""

from __future__ import annotations

import json
import logging
from bdpan_cli.auth import TokenManager
from bdpan_cli.config import load_config
from bdpan_cli.file_manager import FileManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT_UNWATCHED = "/影视/电影/unwatched"


def apply_renames(
    preview_file: str = "scrape_preview.json",
    target_dir: str | None = None,
    batch_size: int = 50,
) -> None:
    config = load_config()
    token = TokenManager(config).get_access_token()
    mgr = FileManager(token)

    with open(preview_file, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    verify_dir = target_dir or (mapping[0].get("parent_dir") if mapping else None) or ROOT_UNWATCHED
    logger.info("正在查询网盘当前 %s 目录下实际存在的条目...", verify_dir)
    current_entries = mgr.list_dir(verify_dir)
    current_names = set(e.get("server_filename") for e in current_entries)
    logger.info("网盘当前 %s 目录下实际存在 %d 个条目", verify_dir, len(current_names))

    rename_items: list[tuple[str, str]] = []
    skipped_items: list[str] = []

    for item in mapping:
        idx = item["index"]
        raw = item["raw_name"]
        target = item["target_name"]
        status = item.get("status")

        if status != "OK" or not target or target.startswith("【"):
            logger.warning("[%d] 跳过未匹配或跳过项 (%s): %s", idx, status, raw)
            skipped_items.append(raw)
            continue

        if raw == target or target in current_names:
            logger.info("[%d] 目标名称已符合规范或已存在，无需更名: %s", idx, target)
            skipped_items.append(raw)
            continue

        if raw not in current_names:
            logger.warning("[%d] 源目录在网盘中不存在，跳过: %s", idx, raw)
            skipped_items.append(raw)
            continue

        src_path = item.get("src_path") or f"{verify_dir}/{raw}"
        rename_items.append((src_path, target))
        logger.info("[%d] 计划更名: %s -> %s", idx, raw, target)

    if not rename_items:
        logger.info("没有需要更名的目录，操作完成。")
        return

    logger.info("准备对 %d 个目录执行批量更名（每批 %d 项）...", len(rename_items), batch_size)
    results = mgr.batch_rename(rename_items, batch_size=batch_size)

    # 统计成功与失败
    success_count = 0
    fail_count = 0
    for r in results:
        info_list = r.get("info", [])
        for inf in info_list:
            if inf.get("errno") == 0:
                success_count += 1
            else:
                fail_count += 1
                logger.error("更名失败项: %s", inf)

    logger.info("=== 批量更名执行完毕: 提交 %d, 成功 %d, 失败 %d, 跳过 %d ===", len(rename_items), success_count, fail_count, len(skipped_items))

    # 执行对账
    logger.info("=== 执行网盘目录更名后对账 ===")
    reconciled_entries = mgr.list_dir(verify_dir)
    logger.info("当前 %s 下共有 %d 个目录：", verify_dir, len(reconciled_entries))
    for i, e in enumerate(reconciled_entries, 1):
        logger.info("  %2d. %s", i, e.get("server_filename"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="执行批量更名")
    parser.add_argument("--preview", default="watched_scrape_preview.json", help="预演映射文件")
    parser.add_argument("--dir", default=None, help="目标目录（可选，若未在 json 中指定）")
    parser.add_argument("--batch-size", type=int, default=25, help="每批重命名数量")
    args = parser.parse_args()
    apply_renames(args.preview, target_dir=args.dir, batch_size=args.batch_size)

