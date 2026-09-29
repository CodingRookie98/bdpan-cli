"""Unit tests for MovieScraper."""

from unittest.mock import MagicMock, patch

import pytest

from bd_net_disc_mgr.scraper import MovieMetadata, MovieScraper


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
