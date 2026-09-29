"""批量刮削预览并生成方案 A 对照表。"""

from __future__ import annotations

import argparse
import json
import logging
import re
from typing import Any

from bdpan_cli.auth import TokenManager
from bdpan_cli.config import load_config
from bdpan_cli.file_manager import FileManager
from bdpan_cli.scraper import MovieScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 方案 A 规范匹配模式（包含 4 位年份与 tt 或 tmdb ID，不含压制发布组标签）
FORMAT_PATTERN = re.compile(
    r"^.+\.(19\d{2}|20[0-3]\d)\.(tt\d{7,8}|tmdb\d+)(\.[A-Za-z0-9_ -]+)*$"
)
NOISE_CHECK = re.compile(
    r"\b(1080p|2160p|720p|BluRay|WEB-DL|WEBRip|x264|x265|HEVC|REMUX|DTS)\b",
    re.IGNORECASE,
)


def is_already_conforming(name: str) -> bool:
    """判断目录名是否已经严格符合方案 A 规范。"""
    return bool(FORMAT_PATTERN.match(name) and not NOISE_CHECK.search(name))


def detect_edition(name: str) -> str:
    """从杂乱文件名中嗅探版本标签，防止同名多版本冲突。"""
    editions = []
    if "AI_UPSCALE" in name:
        editions.append("Extended.AI-Upscale" if re.search(r"加长|Extended|Collector", name, re.I) else "AI-Upscale")
    elif re.search(r"加长|Extended|Collector", name, re.IGNORECASE):
        editions.append("Extended.Collector" if ("收藏" in name or "Collector" in name) else "Extended")
    if re.search(r"删减", name):
        editions.append("Cut")
    if re.search(r"测试", name):
        editions.append("Beta")
    if re.search(r"BONUS", name, re.IGNORECASE):
        editions.append("Bonus")
    if re.search(r"Redux", name, re.IGNORECASE):
        editions.append("Redux")
    if "BONZO" in name:
        editions.append("Remux-BONZO")
    elif "RARBG" in name and "Walter.Mitty" in name:
        editions.append("Remux-RARBG")
    return ".".join(editions)


def generate_preview(
    target_dir: str = "/影视/电影/watched",
    output_file: str = "watched_scrape_preview.json",
    skip_conforming: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    config = load_config()
    token = TokenManager(config).get_access_token()
    mgr = FileManager(token)
    scraper = MovieScraper()

    entries = mgr.list_dir(target_dir)
    if limit:
        entries = entries[:limit]

    logger.info(
        "=== 正在为 %s 目录下 %d 部电影生成方案 A 预演表 (跳过规范项: %s) ===",
        target_dir,
        len(entries),
        skip_conforming,
    )

    mapping: list[dict[str, Any]] = []
    skipped_count = 0
    ok_count = 0
    fail_count = 0

    for i, e in enumerate(entries, 1):
        raw_name = e.get("server_filename")
        if not raw_name:
            continue

        # 检查是否已符合规范
        if skip_conforming and is_already_conforming(raw_name):
            skipped_count += 1
            tt_match = re.search(r"\b(tt\d{7,8}|tmdb\d+)\b", raw_name, re.I)
            record = {
                "index": i,
                "parent_dir": target_dir,
                "src_path": f"{target_dir}/{raw_name}",
                "raw_name": raw_name,
                "target_name": raw_name,
                "imdb_id": tt_match.group(1).lower() if tt_match else None,
                "tmdb_id": None,
                "media_type": "movie",
                "status": "SKIP_CONFORMING",
                "reason": "已符合方案 A 规范，无需更名",
            }
            mapping.append(record)
            logger.info("[%2d/%d] [SKIP] %s (已合规)", i, len(entries), raw_name)
            continue

        edition = detect_edition(raw_name)
        meta = scraper.scrape_folder_name(raw_name, edition_hint=edition)
        if meta:
            target_name = meta.formatted_name
            tmdb_id = meta.tmdb_id
            mtype = meta.media_type
            imdb = meta.imdb_id
            status = "OK"
            ok_count += 1
        else:
            target_name = "【未匹配到，待人工确认】"
            tmdb_id = None
            mtype = None
            imdb = None
            status = "FAIL"
            fail_count += 1

        record = {
            "index": i,
            "parent_dir": target_dir,
            "src_path": f"{target_dir}/{raw_name}",
            "raw_name": raw_name,
            "target_name": target_name,
            "imdb_id": imdb,
            "tmdb_id": tmdb_id,
            "media_type": mtype,
            "status": status,
        }
        mapping.append(record)
        logger.info("[%2d/%d] [%s] %s -> %s", i, len(entries), status, raw_name, target_name)

    # 检查 target_name 冲突
    name_seen: dict[str, list[int]] = {}
    for item in mapping:
        tname = item["target_name"]
        if item["status"] == "OK":
            name_seen.setdefault(tname, []).append(item["index"])

    for tname, indices in name_seen.items():
        if len(indices) > 1:
            logger.warning("发现重名冲突目标: %s 出现在索引 %s", tname, indices)
            for idx in indices:
                mapping[idx - 1]["status"] = "CONFLICT"
                mapping[idx - 1]["reason"] = f"与其他 {len(indices) - 1} 个目录目标重名"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    logger.info("=== 预演完成，已保存至 %s ===", output_file)
    logger.info(
        "统计: 总数=%d | 已合规跳过=%d | 成功匹配=%d | 失败=%d",
        len(entries),
        skipped_count,
        ok_count,
        fail_count,
    )
    return mapping


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量电影刮削预演")
    parser.add_argument("--dir", default="/影视/电影/watched", help="目标目录")
    parser.add_argument("--output", default="watched_scrape_preview.json", help="输出 json 路径")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已合规项")
    parser.add_argument("--limit", type=int, default=None, help="最大处理数量（测试用）")
    args = parser.parse_args()

    generate_preview(
        target_dir=args.dir,
        output_file=args.output,
        skip_conforming=not args.no_skip,
        limit=args.limit,
    )

