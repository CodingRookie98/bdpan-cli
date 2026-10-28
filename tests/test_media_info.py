"""测试媒体深度元数据解析与目录聚合统计模块。"""

from unittest.mock import MagicMock
import pytest

from bdpan_cli.media_info import MediaInfoClient, MediaInfoError


def test_get_media_info_success():
    mock_fm = MagicMock()
    mock_fm.get_file_info.return_value = {
        "fs_id": 123456,
        "path": "/videos/movies/Inception.2010.mkv",
        "server_filename": "Inception.2010.mkv",
        "isdir": 0,
        "size": 15728640000,
        "md5": "abc123def456",
    }

    mock_multimedia_api = MagicMock()
    mock_multimedia_api.xpanmultimediafilemetas.return_value = {
        "errno": 0,
        "list": [
            {
                "fs_id": 123456,
                "server_filename": "Inception.2010.mkv",
                "size": 15728640000,
                "duration": 8880,
                "width": 3840,
                "height": 2160,
                "video_codec": "hevc",
                "media_info": {
                    "video": [{"codec": "hevc", "width": 3840, "height": 2160, "duration": 8880}],
                    "audio": [{"codec": "dts", "channels": 6}],
                },
            }
        ],
    }

    client = MediaInfoClient("fake_token")
    client._file_manager = mock_fm
    client._multimedia_api = mock_multimedia_api

    info = client.get_media_info("/videos/movies/Inception.2010.mkv")

    assert info["path"] == "/videos/movies/Inception.2010.mkv"
    assert info["filename"] == "Inception.2010.mkv"
    assert info["size"] == 15728640000
    assert info["duration_seconds"] == 8880
    assert info["duration_formatted"] == "02:28:00"
    assert info["resolution"] == "3840x2160 (4K UHD)"
    assert info["video_codec"] == "HEVC"
    assert info["is_video"] is True


def test_get_media_info_non_existent():
    mock_fm = MagicMock()
    mock_fm.get_file_info.return_value = None

    client = MediaInfoClient("fake_token")
    client._file_manager = mock_fm

    with pytest.raises(MediaInfoError, match="网盘文件不存在"):
        client.get_media_info("/videos/not_exist.mp4")


def test_get_media_info_is_dir():
    mock_fm = MagicMock()
    mock_fm.get_file_info.return_value = {"isdir": 1, "path": "/videos/movies"}

    client = MediaInfoClient("fake_token")
    client._file_manager = mock_fm

    with pytest.raises(MediaInfoError, match="目标为目录"):
        client.get_media_info("/videos/movies")


def test_get_dir_stats():
    mock_fm = MagicMock()
    # 模拟返回目录树条目列表
    mock_fm.walk.return_value = (
        [
            (0, {"server_filename": "movies", "path": "/movies", "isdir": 1, "size": 0}),
            (1, {"server_filename": "a.mkv", "path": "/movies/a.mkv", "isdir": 0, "size": 1000}),
            (1, {"server_filename": "b.mp4", "path": "/movies/b.mp4", "isdir": 0, "size": 2000}),
            (1, {"server_filename": "c.srt", "path": "/movies/c.srt", "isdir": 0, "size": 300}),
            (1, {"server_filename": "poster.jpg", "path": "/movies/poster.jpg", "isdir": 0, "size": 500}),
            (1, {"server_filename": "extra", "path": "/movies/extra", "isdir": 1, "size": 0}),
            (2, {"server_filename": "d.mkv", "path": "/movies/extra/d.mkv", "isdir": 0, "size": 4000}),
        ],
        [],  # 零错误
    )

    client = MediaInfoClient("fake_token")
    client._file_manager = mock_fm

    stats = client.get_dir_stats("/movies")

    assert stats["root"] == "/movies"
    assert stats["total_files"] == 5
    assert stats["total_dirs"] == 2
    assert stats["total_size"] == 7800
    assert stats["by_extension"][".mkv"]["count"] == 2
    assert stats["by_extension"][".mkv"]["size"] == 5000
    assert stats["by_extension"][".mp4"]["count"] == 1
    assert stats["by_extension"][".srt"]["count"] == 1
    assert stats["by_extension"][".jpg"]["count"] == 1
    assert stats["by_category"]["video"]["count"] == 3
    assert stats["by_category"]["subtitle"]["count"] == 1
    assert stats["by_category"]["image"]["count"] == 1
