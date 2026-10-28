"""Unit tests for Downloader and download/dlink commands (BK-0032)."""

import io
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from bdpan_cli.downloader import DownloadError, Downloader


def _make_downloader():
    mock_client = MagicMock()
    downloader = Downloader("fake-token", mock_client)
    downloader._multimedia_api = MagicMock()
    downloader._file_manager = MagicMock()
    return downloader, downloader._multimedia_api, downloader._file_manager


def test_get_dlink_success():
    downloader, mock_multi, mock_fm = _make_downloader()
    mock_fm.get_file_info.return_value = {
        "fs_id": 12345,
        "path": "/videos/test.mp4",
        "server_filename": "test.mp4",
        "size": 1024,
    }
    mock_multi.xpanmultimediafilemetas.return_value = {
        "errno": 0,
        "list": [
            {
                "fs_id": 12345,
                "dlink": "https://d.pcs.baidu.com/file/abc?sign=xyz",
                "size": 1024,
                "md5": "098f6bcd4621d373cade4e832627b4f6",
            }
        ],
    }

    info = downloader.get_dlink("/videos/test.mp4")
    assert info["dlink"] == "https://d.pcs.baidu.com/file/abc?sign=xyz"
    assert info["size"] == 1024
    mock_multi.xpanmultimediafilemetas.assert_called_once()


def test_get_dlink_not_found():
    downloader, mock_multi, mock_fm = _make_downloader()
    mock_fm.get_file_info.return_value = None

    with pytest.raises(DownloadError) as exc_info:
        downloader.get_dlink("/videos/not_found.mp4")
    assert "不存在" in str(exc_info.value)


def test_generate_export_command_aria2():
    dlink = "https://d.pcs.baidu.com/file/sample.mp4?sign=xyz"
    cmd = Downloader.generate_export_command(dlink, "sample.mp4", style="aria2")
    assert 'aria2c -c -s16 -x16 --header="User-Agent: pan.baidu.com"' in cmd
    assert '"https://d.pcs.baidu.com/file/sample.mp4?sign=xyz"' in cmd
    assert '-o "sample.mp4"' in cmd


def test_generate_export_command_curl():
    dlink = "https://d.pcs.baidu.com/file/sample.mp4?sign=xyz"
    cmd = Downloader.generate_export_command(dlink, "sample.mp4", style="curl")
    assert 'curl -C - -H "User-Agent: pan.baidu.com"' in cmd
    assert '-o "sample.mp4"' in cmd


def test_download_file_fresh(tmp_path):
    downloader, mock_multi, mock_fm = _make_downloader()
    mock_fm.get_file_info.return_value = {
        "fs_id": 999,
        "path": "/movie.mkv",
        "server_filename": "movie.mkv",
        "size": 12,
    }
    mock_multi.xpanmultimediafilemetas.return_value = {
        "errno": 0,
        "list": [{"fs_id": 999, "dlink": "https://d.pcs.baidu.com/movie.mkv", "size": 12}],
    }

    dest_file = tmp_path / "movie.mkv"

    # Mock urllib.request.urlopen
    mock_resp = MagicMock()
    mock_resp.getheader.return_value = "12"
    mock_resp.read.side_effect = [b"hello ", b"world!", b""]
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result_path = downloader.download_file("/movie.mkv", str(dest_file))
        assert os.path.exists(result_path)
        with open(result_path, "rb") as f:
            assert f.read() == b"hello world!"

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("User-agent") == "pan.baidu.com"


def test_download_file_resume(tmp_path):
    downloader, mock_multi, mock_fm = _make_downloader()
    mock_fm.get_file_info.return_value = {
        "fs_id": 888,
        "path": "/partial.mkv",
        "server_filename": "partial.mkv",
        "size": 12,
    }
    mock_multi.xpanmultimediafilemetas.return_value = {
        "errno": 0,
        "list": [{"fs_id": 888, "dlink": "https://d.pcs.baidu.com/partial.mkv", "size": 12}],
    }

    dest_file = tmp_path / "partial.mkv"
    tmp_dest = tmp_path / "partial.mkv.tmp"
    # Pre-write 6 bytes
    with open(tmp_dest, "wb") as f:
        f.write(b"hello ")

    mock_resp = MagicMock()
    mock_resp.getheader.return_value = "6"
    mock_resp.read.side_effect = [b"world!", b""]
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        result_path = downloader.download_file("/partial.mkv", str(dest_file))
        assert os.path.exists(result_path)
        with open(result_path, "rb") as f:
            assert f.read() == b"hello world!"

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Range") == "bytes=6-"
