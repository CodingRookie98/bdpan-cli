"""电影元数据刮削与目录名规范化模块。"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TMDB_TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyMzc1ZGIzOTYwYWVhMWI1OTA1NWMwZmM3ZDcwYjYwZiIsInN1YiI6IjYwYmNhZTk0NGE0YmY2MDA1OWJhNWE1ZSIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.DU51juQWlAIIfZ2lK99b3zi-c5vgc4jAwVz5h2WjOP8"
)


@dataclass
class MovieMetadata:
    """电影元数据模型。"""

    title: str  # 中文译名 / 主标题
    original_title: str  # 外文原名 / 英文名
    year: str  # 上映年份 (YYYY)
    imdb_id: str  # ttXXXXXXX
    tmdb_id: int | None = None
    media_type: str = "movie"  # movie 或 tv
    overview: str = ""  # 剧情简介 (zh-CN 优先)
    poster_path: str = ""  # TMDB 海报相对路径
    edition: str = ""  # 特别版本标识 (若有)

    @property
    def formatted_name(self) -> str:
        """生成方案 A 规范目录名：[中文译名].[英文原名].[上映年份].[IMDb ID]"""

        def sanitize(text: str) -> str:
            cleaned = re.sub(r'[\/\\:\*\?"<>\|\s_,]+', ".", text.strip())
            cleaned = re.sub(r"\.{2,}", ".", cleaned)
            return cleaned.strip(".")

        zh = sanitize(self.title)
        en = sanitize(self.original_title)
        yr = self.year.strip()
        imdb = self.imdb_id.strip() if self.imdb_id else (f"tmdb{self.tmdb_id}" if self.tmdb_id else "")

        # 如果英文名跟中文名完全一样或全为汉字，则仅保留中文名
        is_en_pure_chinese = bool(re.fullmatch(r"[\u4e00-\u9fa5·.]+", en))
        if zh.lower() == en.lower() or not en or is_en_pure_chinese:
            base = f"{zh}.{yr}.{imdb}".strip(".")
        else:
            base = f"{zh}.{en}.{yr}.{imdb}".strip(".")

        if self.edition:
            base = f"{base}.{sanitize(self.edition)}"
        return base


class MovieScraper:
    """TMDB + 豆瓣电影刮削器，支持以 IMDb ID 或标题检索，语言优先 zh-CN，次选 en-US。"""

    def __init__(self, tmdb_token: str = DEFAULT_TMDB_TOKEN) -> None:
        self.tmdb_token = tmdb_token

    def _http_get(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.tmdb_token}",
                "Accept": "application/json",
                "User-Agent": "bd-net-disc-mgr/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _query_douban_title(self, keyword: str) -> str | None:
        """从豆瓣建议接口补全中文片名。"""
        url = f"https://movie.douban.com/j/subject_suggest?q={urllib.parse.quote(keyword)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data and isinstance(data, list):
                    return data[0].get("title")
        except Exception:
            pass
        return None

    def parse_folder_name(self, name: str) -> dict[str, str | None]:
        """解析杂乱的原目录名，提取 IMDb ID、中文片名、外文片名和年份。"""
        # 0. 清理前缀包装，如 "热门 [极速车王 2019]" 与推广后缀 "@公众号..."
        cleaned_name = re.sub(r"@.*$", "", name)
        cleaned_name = re.sub(r"【.*?】", " ", cleaned_name)
        cleaned_name = re.sub(r"^\s*\d{1,2}[\s._\-]+", "", cleaned_name)
        if re.match(r"^(热门|电影|推荐|资源|分享)\s*\[", cleaned_name):
            bracket_m = re.search(r"\[(.*?)\]", cleaned_name)
            if bracket_m:
                cleaned_name = bracket_m.group(1)
        # 拆分附着在单词或汉字后的分辨率与画质标签 (如 NoBody2160p -> NoBody 2160p, 竖锯4K -> 竖锯 4K)
        cleaned_name = re.sub(
            r"(?<=[A-Za-z\u4e00-\u9fa5])(?=(?:4K|2K|8K|\d{3,4}p)\b)",
            " ",
            cleaned_name,
            flags=re.IGNORECASE,
        )
        # 移除 S01 / S02
        cleaned_name = re.sub(r"\bS\d{1,2}\b", " ", cleaned_name)
        # 移除末尾 Team 标识 (如 PHDTeam)
        cleaned_name = re.sub(r"\b[A-Za-z0-9]+Team\b", " ", cleaned_name)

        # 1. 优先提取已有 tt\d+
        tt_match = re.search(r"\b(tt\d{7,8})\b", cleaned_name, re.IGNORECASE)
        imdb_id = tt_match.group(1).lower() if tt_match else None

        # 2. 提取 4 位年份 (1920-2035)
        # 优先提取括号年份 (2018) 或 [2018]
        year = None
        paren = re.search(r"[\(\[]\s*(19\d{2}|20[0-3]\d)\s*[\)\]]", cleaned_name)
        if paren:
            year = paren.group(1)
        else:
            all_years = list(re.finditer(r"\b(19\d{2}|20[0-3]\d)\b", cleaned_name))
            if len(all_years) == 1:
                year = all_years[0].group(1)
            elif len(all_years) > 1:
                # 如果第一个年份位于开头（0..4），且紧接着有第二个年份（如 1917.2019），第一个是片名，第二个是年份
                if all_years[0].start() == 0 and all_years[1].start() <= 10:
                    year = all_years[1].group(1)
                else:
                    year = all_years[-1].group(1)

        # 3. 提取中文字符串
        noise_pattern = re.compile(
            r"\b(1080p|2160p|720p|480p|BluRay|Blu-ray|WEB-DL|WEBRip|HDTV|REMUX|UHD|HDR|DV|DDP\d?\.?\d?|"
            r"Atmos|x264|x265|HEVC|H264|H265|DTS|AAC|TrueHD|FLAC|10bit|60fps|60FPS|REPACK|EXTENDED|"
            r"Director'?s\.?Cut|KORSUB|BDRip|WEB|4K|2K|8K|DCP|Theatrical|Trailer|Hi10p|AC3|BD|DOCU|DVD|Re)\b",
            re.IGNORECASE,
        )
        cleaned_zh = re.sub(
            r"\[.*?(?:字幕|音轨|版本|高码|帧率|双语|国语|原盘|简|繁|英|4K|1080|2160|蓝光).*?\]|\(.*?(?:字幕|音轨|删减).*?\)",
            " ",
            cleaned_name,
        )
        cleaned_zh = noise_pattern.sub(" ", cleaned_zh)
        cleaned_zh = re.sub(r"[._]+", " ", cleaned_zh)
        zh_candidates = re.findall(r"[\u4e00-\u9fa50-9：:·\-—]{2,}", cleaned_zh)
        tag_words = {
            "测试版", "删减版", "合集", "加长收藏版", "蓝光原盘", "中英双字", "国语音轨",
            "高码版", "国语配音", "特效字幕", "内封简英双字", "国语中字", "简繁字幕", "国语", "粤语配音",
        }
        zh_title = None
        for cand in zh_candidates:
            cand_clean = cand.strip("：:·-— ")
            if any("\u4e00" <= ch <= "\u9fa5" for ch in cand_clean) and cand_clean not in tag_words:
                zh_title = cand_clean
                break

        # 4. 提取外文主要名称
        text = re.sub(r"\[.*?\]|\(.*?\)", " ", cleaned_name)
        text = re.sub(r"[._]+", " ", text)

        def _clean_cand(raw: str) -> str:
            cand = noise_pattern.sub(" ", raw)
            cand = re.sub(r"[\u4e00-\u9fa5·：:（\(\)）\[\]【】、]+", " ", cand)
            cand = re.sub(r"[-@][A-Za-z0-9_]+$", "", cand)
            if " - " in cand:
                after_dash = cand.split(" - ")[-1].strip()
                if after_dash and re.search(r"[A-Za-z]", after_dash):
                    cand = after_dash
            cand = re.sub(r"\b(JAPANESE|KOREAN|GERMAN|FRENCH|ITALIAN|RUSSIAN|CHINESE)\b", " ", cand, flags=re.I)
            return " ".join(cand.split())

        def _is_valid_en(w: str) -> bool:
            if not w:
                return False
            has_word = bool(re.search(r"\b[A-Za-z]{2,}\b", w))
            is_valid_num = bool(w.isdigit() and len(w) >= 3 and w != year)
            return has_word or is_valid_num

        en_title = None
        if year and year in text:
            parts = text.split(year)
            before = parts[0].strip()
            after = parts[1].strip() if len(parts) > 1 else ""
            if before:
                words = _clean_cand(before)
                if _is_valid_en(words):
                    en_title = words
            elif after:
                words = _clean_cand(after)
                if _is_valid_en(words):
                    en_title = words

        if not en_title:
            noise_m = noise_pattern.search(text)
            cand_raw = text[:noise_m.start()] if noise_m else text
            words = _clean_cand(cand_raw)
            if _is_valid_en(words):
                en_title = words

        return {
            "imdb_id": imdb_id,
            "year": year,
            "zh_title": zh_title,
            "en_title": en_title,
        }

    def _extract_detail_meta(
        self,
        media_type: str,
        tmdb_id: int,
        item: dict[str, Any],
        imdb_id_hint: str = "",
        fallback_zh: str | None = None,
        fallback_en: str | None = None,
    ) -> MovieMetadata:
        """从 TMDB 详情与 translations 中提炼最优质的中文与英文名。"""
        detail_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?append_to_response=external_ids,translations&language=zh-CN"
        try:
            detail = self._http_get(detail_url)
        except Exception:
            detail = item

        imdb_id = (
            detail.get("external_ids", {}).get("imdb_id")
            or detail.get("imdb_id")
            or imdb_id_hint
            or ""
        )
        rel_date = (
            detail.get("release_date")
            or detail.get("first_air_date")
            or item.get("release_date")
            or item.get("first_air_date")
            or ""
        )
        year = rel_date[:4] if rel_date else ""
        overview = detail.get("overview") or item.get("overview") or ""
        poster_path = detail.get("poster_path") or item.get("poster_path") or ""

        # 解析多语言 translations
        trans_list = detail.get("translations", {}).get("translations", [])
        zh_cn_title = None
        zh_other_title = None
        en_trans_title = None
        for t in trans_list:
            iso = t.get("iso_3166_1")
            iso_lang = t.get("iso_639_1")
            data = t.get("data", {})
            title_or_name = (data.get("title") or data.get("name") or "").strip()
            if not title_or_name:
                continue
            if iso == "CN" and not zh_cn_title:
                zh_cn_title = title_or_name
            elif iso_lang == "zh" and not zh_other_title:
                zh_other_title = title_or_name
            elif iso in ("US", "GB") and iso_lang == "en" and not en_trans_title:
                en_trans_title = title_or_name

        zh_trans_title = zh_cn_title or zh_other_title

        # 决定中文名
        zh_title = (
            zh_trans_title
            or detail.get("title")
            or detail.get("name")
            or item.get("title")
            or item.get("name")
            or fallback_zh
            or ""
        )
        # 如果依然没有中文字符（例如韩文原名），尝试用英文名或原名从豆瓣建议接口补齐
        if not re.search(r"[\u4e00-\u9fa5]", zh_title):
            douban_q = en_trans_title or fallback_en or detail.get("original_title") or fallback_zh or ""
            douban_zh = self._query_douban_title(douban_q)
            if douban_zh:
                zh_title = douban_zh

        # 决定英文名 / 原名
        orig_title = (
            detail.get("original_title")
            or detail.get("original_name")
            or item.get("original_title")
            or item.get("original_name")
            or ""
        ).strip()
        is_orig_latin = bool(
            orig_title
            and re.search(r"[A-Za-z]", orig_title)
            and not re.search(r"[\uAC00-\uD7A3\u3040-\u30FF\u0400-\u04FF\u4E00-\u9FA5]", orig_title)
        )

        # 英文名策略：
        # 1. 若原名本身就是拉丁/英文原名（如 Toy Story, Contact），直接采信原名
        if is_orig_latin:
            en_title = orig_title
        # 2. 否则优先选用经校验为英语的翻译名称
        elif en_trans_title and re.search(r"[A-Za-z]", en_trans_title):
            en_title = en_trans_title
        # 3. 再次选用有效英文 fallback_en
        elif fallback_en and re.search(r"\b[A-Za-z]{2,}\b", fallback_en):
            en_title = fallback_en
        else:
            en_title = en_trans_title or orig_title or fallback_en or ""

        return MovieMetadata(
            title=zh_title,
            original_title=en_title,
            year=year,
            imdb_id=imdb_id,
            tmdb_id=tmdb_id,
            media_type=media_type,
            overview=overview,
            poster_path=poster_path,
        )

    def fetch_by_imdb_id(
        self,
        imdb_id: str,
        fallback_zh: str | None = None,
        fallback_en: str | None = None,
    ) -> MovieMetadata | None:
        """通过 IMDb ID 在 TMDB 精准反查电影/剧集详情。"""
        url = f"https://api.themoviedb.org/3/find/{imdb_id}?external_source=imdb_id&language=zh-CN"
        try:
            data = self._http_get(url)
        except Exception as e:
            logger.warning("通过 IMDb ID %s 查询 TMDB 失败: %s", imdb_id, e)
            return None

        results = data.get("movie_results", [])
        media_type = "movie"
        if not results:
            results = data.get("tv_results", [])
            media_type = "tv"
        if not results:
            return None

        item = results[0]
        return self._extract_detail_meta(
            media_type=media_type,
            tmdb_id=item["id"],
            item=item,
            imdb_id_hint=imdb_id,
            fallback_zh=fallback_zh,
            fallback_en=fallback_en,
        )

    def search_movie(
        self,
        title: str,
        year: str | None = None,
        fallback_zh: str | None = None,
        fallback_en: str | None = None,
    ) -> MovieMetadata | None:
        """通过标题和年份在 TMDB 搜索电影，并按 vote_count 排序命中代表作。"""
        encoded_q = urllib.parse.quote(title)
        url = f"https://api.themoviedb.org/3/search/movie?query={encoded_q}&language=zh-CN"
        if year:
            url += f"&primary_release_year={year}"

        try:
            data = self._http_get(url)
        except Exception as e:
            logger.warning("搜索 TMDB 失败 [%s, %s]: %s", title, year, e)
            return None

        results = data.get("results", [])
        if not results and year:
            # 尝试去掉年份再搜
            url_no_yr = f"https://api.themoviedb.org/3/search/movie?query={encoded_q}&language=zh-CN"
            try:
                data = self._http_get(url_no_yr)
                results = data.get("results", [])
            except Exception:
                pass

        media_type = "movie"
        if not results:
            tv_url = f"https://api.themoviedb.org/3/search/tv?query={encoded_q}&language=zh-CN"
            if year:
                tv_url += f"&first_air_date_year={year}"
            try:
                tv_data = self._http_get(tv_url)
                results = tv_data.get("results", [])
                if not results and year:
                    tv_url_no_yr = f"https://api.themoviedb.org/3/search/tv?query={encoded_q}&language=zh-CN"
                    tv_data = self._http_get(tv_url_no_yr)
                    results = tv_data.get("results", [])
                if results:
                    media_type = "tv"
            except Exception:
                pass

        if not results:
            return None

        # 核心优化：年份匹配优先，有效投票数优先，完全匹配标题优先，其次按 vote_count 与 popularity 综合排序
        def rank_key(item_dict: dict[str, Any]) -> tuple[int, int, int, int, float]:
            t = (item_dict.get("title") or item_dict.get("name") or "").strip().lower()
            ot = (item_dict.get("original_title") or item_dict.get("original_name") or "").strip().lower()
            q = title.strip().lower()
            is_exact = 1 if (t == q or ot == q) else 0
            rel_year = (item_dict.get("release_date") or item_dict.get("first_air_date") or "")[:4]
            year_matches = 1 if (year and rel_year == str(year)) else 0
            votes = item_dict.get("vote_count", 0)
            has_votes = 1 if votes >= 5 else 0
            return (year_matches, has_votes, is_exact, votes, item_dict.get("popularity", 0.0))

        sorted_results = sorted(results, key=rank_key, reverse=True)
        best_item = sorted_results[0]
        return self._extract_detail_meta(
            media_type=media_type,
            tmdb_id=best_item["id"],
            item=best_item,
            fallback_zh=fallback_zh,
            fallback_en=fallback_en,
        )

    def scrape_folder_name(self, folder_name: str, edition_hint: str = "") -> MovieMetadata | None:
        """主入口：输入目录名，刮削返回标准 MovieMetadata。"""
        parsed = self.parse_folder_name(folder_name)

        meta: MovieMetadata | None = None
        # 1. 优先命中 IMDb ID
        if parsed.get("imdb_id"):
            meta = self.fetch_by_imdb_id(
                parsed["imdb_id"],
                fallback_zh=parsed.get("zh_title"),
                fallback_en=parsed.get("en_title"),
            )

        # 2. 特殊中文片名优先搜索
        if not meta and parsed.get("zh_title"):
            meta = self.search_movie(
                parsed["zh_title"],
                parsed.get("year"),
                fallback_zh=parsed.get("zh_title"),
                fallback_en=parsed.get("en_title"),
            )

        # 3. 英文名搜索
        if not meta and parsed.get("en_title"):
            meta = self.search_movie(
                parsed["en_title"],
                parsed.get("year"),
                fallback_zh=parsed.get("zh_title"),
                fallback_en=parsed.get("en_title"),
            )

        if meta and edition_hint:
            meta.edition = edition_hint

        return meta
