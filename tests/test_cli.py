from unittest.mock import MagicMock, patch
import pytest

from bdpan_cli.cli import build_parser, main
from bdpan_cli.file_manager import FileManagerError


def test_cli_parser_help():
    parser = build_parser()
    assert "ls" in parser._subparsers._group_actions[0].choices
    assert "mkdir" in parser._subparsers._group_actions[0].choices
    assert "mv" in parser._subparsers._group_actions[0].choices
    assert "scrape" in parser._subparsers._group_actions[0].choices
    assert "meta" in parser._subparsers._group_actions[0].choices


def test_cli_backward_compatibility_ls(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [
            {"server_filename": "movie1", "isdir": 1, "size": 0},
            {"server_filename": "movie2.mkv", "isdir": 0, "size": 1048576},
        ]
        mock_mgr_getter.return_value = mock_mgr

        # 传递根路径或目录路径时，应自动解析为 ls
        exit_code = main(["/影视/电影"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "目录: /影视/电影" in captured.out
        assert "movie1" in captured.out
        assert "movie2.mkv" in captured.out


def test_cli_mkdir(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mkdir", "/影视/电影/test_dir"])
        assert exit_code == 0
        mock_mgr.mkdir.assert_called_once_with("/影视/电影/test_dir")


def test_cli_mv(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mv", "/tmp/a.mkv", "/影视/电影/dest"])
        assert exit_code == 0
        mock_mgr.batch_move.assert_called_once_with([("/tmp/a.mkv", "/影视/电影/dest", "a.mkv")])


def test_cli_cp_into_existing_dir(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = []  # dest 是已存在的（空）目录
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/src/movie", "/dst-dir"])
        assert exit_code == 0
        mock_mgr.copy.assert_called_once_with("/src/movie", "/dst-dir", "movie")


def test_cli_cp_with_rename(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        # list_dir 失败 → dest 不是已存在目录，视为完整目标路径
        mock_mgr.list_dir.side_effect = FileManagerError("读取目录失败")
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/src/movie", "/dst/new-name"])
        assert exit_code == 0
        mock_mgr.copy.assert_called_once_with("/src/movie", "/dst", "new-name")


def test_cli_cp_trailing_slash(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/src/movie", "/dst-dir/"])
        assert exit_code == 0
        # 尾斜杠直接视为目录语义，不发起 list_dir 探测
        mock_mgr.list_dir.assert_not_called()
        mock_mgr.copy.assert_called_once_with("/src/movie", "/dst-dir", "movie")


def test_cli_cp_root_level_rename(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.side_effect = FileManagerError("读取目录失败")
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/src/movie", "/top-copy"])
        assert exit_code == 0
        # 根层级目标：dirname 为 /
        mock_mgr.copy.assert_called_once_with("/src/movie", "/", "top-copy")
