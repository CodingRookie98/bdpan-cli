from unittest.mock import MagicMock, patch
import pytest

from bdpan_cli.cli import build_parser, main


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
