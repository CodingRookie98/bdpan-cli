"""Unit tests for the BaiduPan high-level Python SDK client (BK-0045)."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from bdpan_cli.client import BaiduPan
from bdpan_cli.config import AppConfig


def test_client_init_with_explicit_token():
    """验证使用显式 access_token 初始化客户端。"""
    pan = BaiduPan(access_token="test_token_123")
    assert pan.access_token == "test_token_123"
    assert pan.token_manager is None
    assert pan.list_accounts() == [{"account": "explicit_token", "is_current": True, "valid": True}]

    with pytest.raises(RuntimeError) as exc_info:
        pan.switch_account("other")
    assert "不支持账号切换" in str(exc_info.value)


def test_client_init_with_explicit_keys():
    """验证传入 app_key 与 secret_key 初始化客户端。"""
    with patch("bdpan_cli.client.TokenManager") as mock_tm_cls:
        mock_tm = MagicMock()
        mock_tm.get_access_token.return_value = "token_from_keys"
        mock_tm_cls.return_value = mock_tm

        pan = BaiduPan(app_key="my_key", secret_key="my_secret")
        assert pan.access_token == "token_from_keys"
        assert pan.token_manager == mock_tm
        mock_tm_cls.assert_called_once_with(
            AppConfig(app_key="my_key", secret_key="my_secret"),
            account=None,
            cache_path=None,
        )


def test_client_init_auto_config(monkeypatch):
    """验证零参数调用时自动加载配置。"""
    monkeypatch.setenv("BAIDU_APP_KEY", "env_key")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "env_secret")

    with patch("bdpan_cli.client.TokenManager") as mock_tm_cls:
        mock_tm = MagicMock()
        mock_tm.get_access_token.return_value = "auto_token"
        mock_tm_cls.return_value = mock_tm

        pan = BaiduPan()
        assert pan.access_token == "auto_token"


def test_client_subclient_properties():
    """验证底层客户端属性访问（FileManager, Uploader, Downloader, AccountClient, MediaInfoClient）。"""
    pan = BaiduPan(access_token="test_token")
    assert pan.files.access_token == "test_token"
    assert pan.uploader.access_token == "test_token"
    assert pan.downloader.access_token == "test_token"
    assert pan.account.access_token == "test_token"
    assert pan.media.access_token == "test_token"


def test_client_file_operations():
    """验证常用文件操作方法代理（list_dir, mkdir, rename, search, delete, tree）。"""
    pan = BaiduPan(access_token="test_token")

    with patch.object(pan, "files") as mock_files:
        mock_files.list_dir.return_value = [{"server_filename": "demo.txt"}]
        mock_files.mkdir.return_value = {"errno": 0}
        mock_files.rename.return_value = {"errno": 0}
        mock_files.search.return_value = [{"server_filename": "res.txt"}]
        mock_files.delete.return_value = {"errno": 0}
        mock_files.batch_delete.return_value = {"errno": 0}
        mock_files.walk.return_value = ([(1, {"path": "/a.txt"}), (2, {"path": "/b.txt"})], [])
        mock_files.get_file_info.return_value = {"size": 1024}

        # ls & list_dir
        assert pan.list_dir("/test") == [{"server_filename": "demo.txt"}]
        assert pan.ls("/test") == [{"server_filename": "demo.txt"}]
        mock_files.list_dir.assert_called_with(dir_path="/test", limit=1000)

        # get_file_info
        assert pan.get_file_info("/a.txt") == {"size": 1024}

        # mkdir & rename & search
        assert pan.mkdir("/new_dir") == {"errno": 0}
        assert pan.rename("/a", "b") == {"errno": 0}
        assert pan.search("keyword") == [{"server_filename": "res.txt"}]

        # rm & delete (单项与批量)
        assert pan.delete("/del.txt") == {"errno": 0}
        mock_files.delete.assert_called_once_with("/del.txt")

        assert pan.rm(["/d1.txt", "/d2.txt"]) == {"errno": 0}
        mock_files.batch_delete.assert_called_once_with(["/d1.txt", "/d2.txt"])

        # tree
        tree_res = pan.tree("/root", max_depth=2)
        assert tree_res == [{"path": "/a.txt"}, {"path": "/b.txt"}]
        mock_files.walk.assert_called_once_with(root="/root", max_depth=2)


def test_client_move_and_copy():
    """验证 move/mv 与 copy/cp 便捷方法。"""
    pan = BaiduPan(access_token="test_token")

    with patch.object(pan, "files") as mock_files:
        mock_files.batch_move.return_value = {"errno": 0}
        mock_files.copy.return_value = {"errno": 0}
        mock_files.batch_copy.return_value = {"errno": 0}

        # 1. move 单文件到目录
        pan.move("/source/test.txt", "/target/")
        mock_files.batch_move.assert_called_with([{"path": "/source/test.txt", "dest": "/target", "newname": "test.txt"}])

        # 2. move 单文件重命名
        pan.mv("/source/test.txt", "/target/renamed.txt")
        mock_files.batch_move.assert_called_with([{"path": "/source/test.txt", "dest": "/target", "newname": "renamed.txt"}])

        # 3. move 批量文件
        pan.move(["/s1.txt", "/s2.txt"], "/target")
        mock_files.batch_move.assert_called_with([
            {"path": "/s1.txt", "dest": "/target", "newname": "s1.txt"},
            {"path": "/s2.txt", "dest": "/target", "newname": "s2.txt"},
        ])

        # 4. copy 单文件
        pan.copy("/source/test.txt", "/target", new_name="copied.txt")
        mock_files.copy.assert_called_with(path="/source/test.txt", dest_dir="/target", new_name="copied.txt")

        # 5. copy 批量文件
        pan.cp(["/s1.txt", "/s2.txt"], "/target")
        mock_files.batch_copy.assert_called_with([
            {"path": "/s1.txt", "dest": "/target", "newname": "s1.txt"},
            {"path": "/s2.txt", "dest": "/target", "newname": "s2.txt"},
        ])


def test_client_transfer_methods():
    """验证 upload, download, get_download_url 代理。"""
    pan = BaiduPan(access_token="test_token")

    with patch.object(pan, "uploader") as mock_uploader, \
         patch.object(pan, "downloader") as mock_downloader:

        mock_uploader.upload.return_value = {"fs_id": 12345, "errno": 0}
        mock_downloader.download_file.return_value = Path("/tmp/downloaded.mkv")
        mock_downloader.get_dlink.return_value = {"dlink": "https://d.pcs.baidu.com/file/xxx"}

        # upload
        up_res = pan.upload("local.txt", remote_dir="/remote", overwrite=True)
        assert up_res["fs_id"] == 12345
        mock_uploader.upload.assert_called_once_with(
            local_path="local.txt",
            remote_dir="/remote",
            remote_filename=None,
            overwrite=True,
            state_file=None,
            on_progress=None,
        )

        # download
        dl_res = pan.download("/remote/video.mkv", dest_dir="/local/dir", overwrite=False)
        assert dl_res == Path("/tmp/downloaded.mkv")
        mock_downloader.download_file.assert_called_once_with(
            remote_path="/remote/video.mkv",
            dest_dir="/local/dir",
            overwrite=False,
            chunk_size=4 * 1024 * 1024,
            on_progress=None,
        )

        # get_download_url
        dlink = pan.get_download_url("/remote/video.mkv")
        assert dlink == "https://d.pcs.baidu.com/file/xxx"


def test_client_account_and_media():
    """验证 whoami, quota, get_media_info, get_dir_stats 代理。"""
    pan = BaiduPan(access_token="test_token")

    with patch.object(pan, "account") as mock_account, \
         patch.object(pan, "media") as mock_media:

        mock_account.user_info.return_value = {"baidu_name": "developer", "vip_type": 2}
        mock_account.quota.return_value = {"total": 1000000, "used": 500000}
        mock_media.get_media_info.return_value = {"resolution": "4K UHD", "duration": "02:15:30"}
        mock_media.get_dir_stats.return_value = {"total_size": 2048000, "total_files": 42}

        assert pan.whoami() == {"baidu_name": "developer", "vip_type": 2}
        assert pan.get_quota() == {"total": 1000000, "used": 500000}
        assert pan.get_media_info("/movie.mkv") == {"resolution": "4K UHD", "duration": "02:15:30"}
        assert pan.get_dir_stats("/movies", max_depth=1) == {"total_size": 2048000, "total_files": 42}
