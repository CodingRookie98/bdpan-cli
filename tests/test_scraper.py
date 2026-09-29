"""Unit tests for MovieScraper."""

from unittest.mock import MagicMock, patch

import pytest

from bdpan_cli.scraper import MovieMetadata, MovieScraper


def test_movie_metadata_formatted_name():
    meta = MovieMetadata(
        title="芭蕾复仇曲",
        original_title="Ballerina",
        year="2023",
        imdb_id="tt26350277",
    )
    assert meta.formatted_name == "芭蕾复仇曲.Ballerina.2023.tt26350277"


def test_movie_metadata_formatted_name_with_edition():
    meta = MovieMetadata(
        title="白日梦想家",
        original_title="The Secret Life of Walter Mitty",
        year="2013",
        imdb_id="tt0359950",
        edition="Remux-BONZO",
    )
    assert meta.formatted_name == "白日梦想家.The.Secret.Life.of.Walter.Mitty.2013.tt0359950.Remux-BONZO"


def test_movie_metadata_chinese_only():
    meta = MovieMetadata(
        title="大闹天宫",
        original_title="大闹天宫",
        year="1961",
        imdb_id="tt0059855",
    )
    # 当原名与中文名相同时不重复
    assert meta.formatted_name == "大闹天宫.1961.tt0059855"


def test_parse_folder_name_with_tt():
    scraper = MovieScraper()
    parsed = scraper.parse_folder_name("美丽心灵.A.Beautiful.Mind.2001.tt0268978")
    assert parsed["imdb_id"] == "tt0268978"
    assert parsed["year"] == "2001"
    assert parsed["zh_title"] == "美丽心灵"


def test_parse_folder_name_release_group():
    scraper = MovieScraper()
    parsed = scraper.parse_folder_name("Contact (1997) (1080p BluRay x265 10bit AAC 5.1 afm72)")
    assert parsed["imdb_id"] is None
    assert parsed["year"] == "1997"
    assert parsed["en_title"] == "Contact"


def test_parse_folder_name_chinese_with_tags():
    scraper = MovieScraper()
    parsed = scraper.parse_folder_name("芙蓉镇[国语音轨+简英字幕].Hibiscus.Town.1987.UHD.BluRay.2160p")
    assert parsed["zh_title"] == "芙蓉镇"
    assert parsed["year"] == "1987"


@patch.object(MovieScraper, "_http_get")
def test_fetch_by_imdb_id(mock_http):
    mock_http.return_value = {
        "movie_results": [
            {
                "id": 686,
                "title": "超时空接触",
                "original_title": "Contact",
                "release_date": "1997-07-11",
                "overview": "简介内容",
                "poster_path": "/contact.jpg",
            }
        ]
    }
    scraper = MovieScraper()
    meta = scraper.fetch_by_imdb_id("tt0118884")
    assert meta is not None
    assert meta.title == "超时空接触"
    assert meta.original_title == "Contact"
    assert meta.year == "1997"
    assert meta.imdb_id == "tt0118884"
    assert meta.formatted_name == "超时空接触.Contact.1997.tt0118884"


def test_parse_folder_name_consecutive_years_1917():
    scraper = MovieScraper()
    parsed = scraper.parse_folder_name("1917.2019.2160p.UHD.BluRay.x265.10bit.HDR.DTS-HD.MA.TrueHD.7.1.Atmos-SWTYBLZ")
    assert parsed["year"] == "2019"
    assert parsed["en_title"] == "1917"


def test_parse_folder_name_foreign_dash_english():
    scraper = MovieScraper()
    parsed = scraper.parse_folder_name("Atomica Bionda - Atomic Blonde (2017) 2160p H265 10 bit ita eng AC3 5.1 sub ita eng Licdom")
    assert parsed["year"] == "2017"
    assert parsed["en_title"] == "Atomic Blonde"


def test_parse_folder_name_leading_number_chinese():
    scraper = MovieScraper()
    parsed = scraper.parse_folder_name("7号房的礼物.Find.Miracle.in.Cell.No.7.2013.tt2659414")
    assert parsed["zh_title"] == "7号房的礼物"
    assert parsed["year"] == "2013"
    assert parsed["imdb_id"] == "tt2659414"


def test_movie_metadata_formatted_name_tmdb_fallback():
    meta = MovieMetadata(
        title="香港女星图鉴",
        original_title="The Illustrated Guide to Hong Kong Stars",
        year="1991",
        imdb_id="",
        tmdb_id=1355314,
    )
    assert meta.formatted_name == "香港女星图鉴.The.Illustrated.Guide.to.Hong.Kong.Stars.1991.tmdb1355314"


@patch.object(MovieScraper, "_http_get")
def test_search_movie_prioritizes_release_year(mock_http):
    # 模拟 TMDB 返回两个阿拉丁：1992 年（投票数更多）与 2019 年（与指定年份匹配）
    mock_http.side_effect = [
        {
            "results": [
                {"id": 812, "title": "阿拉丁", "original_title": "Aladdin", "release_date": "1992-11-25", "vote_count": 12000, "popularity": 50.0},
                {"id": 420817, "title": "阿拉丁", "original_title": "Aladdin", "release_date": "2019-05-22", "vote_count": 10000, "popularity": 60.0},
            ]
        },
        {
            "id": 420817,
            "title": "阿拉丁",
            "original_title": "Aladdin",
            "release_date": "2019-05-22",
            "external_ids": {"imdb_id": "tt6139732"},
            "translations": {"translations": []},
        },
    ]
    scraper = MovieScraper()
    meta = scraper.search_movie("Aladdin", year="2019")
    assert meta is not None
    assert meta.tmdb_id == 420817
    assert meta.year == "2019"
    assert meta.imdb_id == "tt6139732"

