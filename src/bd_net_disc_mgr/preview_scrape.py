"""批量刮削预览并生成方案 A 对照表。"""

from __future__ import annotations

import json
from bd_net_disc_mgr.auth import TokenManager
from bd_net_disc_mgr.config import load_config
from bd_net_disc_mgr.file_manager import FileManager
from bd_net_disc_mgr.scraper import MovieScraper


def generate_preview():
    config = load_config()
    token = TokenManager(config).get_access_token()
    mgr = FileManager(token)
    scraper = MovieScraper()

    entries = mgr.list_dir("/影视/电影/unwatched")
    print(f"=== 正在为 unwatched 目录下 {len(entries)} 部电影生成方案 A 预演表 ===\n")

    mapping = []
    for i, e in enumerate(entries, 1):
        raw_name = e.get("server_filename")
        edition = ""
        if "BONZO" in raw_name:
            edition = "Remux-BONZO"
        elif "RARBG" in raw_name and "Walter.Mitty" in raw_name:
            edition = "Remux-RARBG"

        meta = scraper.scrape_folder_name(raw_name, edition_hint=edition)
        if meta:
            target_name = meta.formatted_name
            tmdb_id = meta.tmdb_id
            mtype = meta.media_type
            imdb = meta.imdb_id
            status = "OK"
        else:
            target_name = "【未匹配到】"
            tmdb_id = None
            mtype = None
            imdb = None
            status = "FAIL"

        mapping.append({
            "index": i,
            "raw_name": raw_name,
            "target_name": target_name,
            "imdb_id": imdb,
            "tmdb_id": tmdb_id,
            "media_type": mtype,
            "status": status,
        })
        print(f"[{i:2d}/{len(entries)}] {status}")
        print(f"   原名: {raw_name}")
        print(f"   拟改: {target_name}")
        print(f"   标识: IMDb={imdb} | TMDB={tmdb_id} ({mtype})\n")

    # 保存映射到本地 json
    with open("scrape_preview.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print("=== 预演完成，已保存至 scrape_preview.json ===")


if __name__ == "__main__":
    generate_preview()
