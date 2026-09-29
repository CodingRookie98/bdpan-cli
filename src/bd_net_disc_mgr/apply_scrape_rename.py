"""依据审核后的 scrape_preview.json 执行网盘目录批量重命名。"""

from __future__ import annotations

import json
import logging
from bd_net_disc_mgr.auth import TokenManager
from bd_net_disc_mgr.config import load_config
from bd_net_disc_mgr.file_manager import FileManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT_UNWATCHED = "/影视/电影/unwatched"


def apply_renames(preview_file: str = "scrape_preview.json") -> None:
    config = load_config()
    token = TokenManager(config).get_access_token()
    mgr = FileManager(token)

    with open(preview_file, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    logger.info("读取到 %d 项更名映射记录...", len(mapping))

    rename_items: list[tuple[str, str]] = []
    skipped_items: list[str] = []

    for item in mapping:
        idx = item["index"]
        raw = item["raw_name"]
        target = item["target_name"]
        if item.get("status") != "OK" or not target or target.startswith("【"):
            logger.warning("[%d] 跳过未匹配项: %s", idx, raw)
            skipped_items.append(raw)
            continue

        if raw == target:
            logger.info("[%d] 名称已符合规范，无需更名: %s", idx, raw)
            skipped_items.append(raw)
            continue

        src_path = f"{ROOT_UNWATCHED}/{raw}"
        rename_items.append((src_path, target))
        logger.info("[%d/36] 计划更名: %s -> %s", idx, raw, target)

    if not rename_items:
        logger.info("没有需要更名的目录，操作完成。")
        return

    logger.info("准备对 %d 个目录执行批量更名...", len(rename_items))
    results = mgr.batch_rename(rename_items, batch_size=50)

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
    current_entries = mgr.list_dir(ROOT_UNWATCHED)
    logger.info("当前 %s 下共有 %d 个目录：", ROOT_UNWATCHED, len(current_entries))
    for i, e in enumerate(current_entries, 1):
        logger.info("  %2d. %s", i, e.get("server_filename"))


if __name__ == "__main__":
    apply_renames()
