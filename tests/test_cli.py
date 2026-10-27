from unittest.mock import MagicMock, patch
import logging
import pytest

from bdpan_cli.cli import build_parser, main, _resolve_dest
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


def test_cli_ls_non_existent_path(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        # 第一次读 /not_exist 返回空列表，第二次读父目录 / 返回没有 not_exist 的列表
        mock_mgr.list_dir.side_effect = [
            [],
            [{"server_filename": "other_dir", "path": "/other_dir", "isdir": 1}],
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["ls", "/not_exist"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "❌ 路径不存在: /not_exist" in captured.out


def test_cli_ls_empty_existing_dir(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.side_effect = [
            [],
            [{"server_filename": "empty_dir", "path": "/empty_dir", "isdir": 1}],
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["ls", "/empty_dir"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "目录: /empty_dir" in captured.out
        assert "共 0 项" in captured.out


def test_cli_ls_file_path(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.side_effect = [
            [],
            [{"server_filename": "video.mkv", "path": "/video.mkv", "isdir": 0, "size": 1048576}],
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["ls", "/video.mkv"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "📄 文件: /video.mkv" in captured.out



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
        # dest 为已存在目录（父目录列表含 dest 且 isdir=1）→ 移入保名
        mock_mgr.list_dir.return_value = [{"path": "/影视/电影/dest", "isdir": 1}]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mv", "/tmp/a.mkv", "/影视/电影/dest"])
        assert exit_code == 0
        mock_mgr.batch_move.assert_called_once_with([("/tmp/a.mkv", "/影视/电影/dest", "a.mkv")])


def test_cli_cp_into_existing_dir(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        # 父目录列表中存在 dest 且为目录 → 复制入内
        mock_mgr.list_dir.return_value = [{"path": "/dst-dir", "isdir": 1}]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/src/movie", "/dst-dir"])
        assert exit_code == 0
        mock_mgr.copy.assert_called_once_with("/src/movie", "/dst-dir", "movie")


def test_cli_cp_with_rename(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        # 父目录可读但列表中无 dest → dest 不存在，视为 目标目录/新名
        mock_mgr.list_dir.return_value = []
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
        mock_mgr.list_dir.return_value = []
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/src/movie", "/top-copy"])
        assert exit_code == 0
        # 根层级目标：dirname 为 /
        mock_mgr.copy.assert_called_once_with("/src/movie", "/", "top-copy")


def test_cli_cp_dest_parent_unreadable_falls_back_with_warning(caplog):
    mock_mgr = MagicMock()
    # 父目录不可读 → 改名语义 fallback，且补 WARNING 日志
    mock_mgr.list_dir.side_effect = FileManagerError("读取目录失败 [/dst]: 31066 body")

    with caplog.at_level(logging.WARNING, logger="bdpan_cli.cli"):
        dest_dir, dest_name = _resolve_dest(mock_mgr, "/src/movie", "/dst/new-name")

    assert (dest_dir, dest_name) == ("/dst", "new-name")
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "/dst" in caplog.text


def test_cli_rm_yes_flag(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["rm", "-y", "/a", "/b"])
        assert exit_code == 0
        assert [c.args[0] for c in mock_mgr.delete.call_args_list] == ["/a", "/b"]


def test_cli_rm_confirm_yes(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["rm", "/del-target"])
        assert exit_code == 0
        mock_mgr.delete.assert_called_once_with("/del-target")


def test_cli_rm_confirm_abort(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["rm", "/del-target"])
        assert exit_code == 0
        mock_mgr.delete.assert_not_called()


@pytest.mark.parametrize("stdin_error", [EOFError, KeyboardInterrupt])
def test_cli_rm_confirm_stdin_guard(capsys, monkeypatch, stdin_error):
    # 非交互 stdin (EOF) 或 Ctrl-C 时不产生裸 traceback，视作取消
    def _raise(_prompt):
        raise stdin_error

    monkeypatch.setattr("builtins.input", _raise)
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["rm", "/del-target"])
        assert exit_code == 0
        mock_mgr.delete.assert_not_called()


def test_cli_rm_delete_failure(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.delete.side_effect = FileManagerError("删除失败")
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["rm", "-y", "/broken"])
        assert exit_code == 1


def test_cli_rename(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["rename", "/movies/old-name", "new-name"])
        assert exit_code == 0
        mock_mgr.rename.assert_called_once_with("/movies/old-name", "new-name")


def test_cli_mv_move_and_rename(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        # 父目录可读但列表中无 dest → 移动并改名
        mock_mgr.list_dir.return_value = []
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mv", "/a/b.txt", "/c/d.txt"])
        assert exit_code == 0
        mock_mgr.batch_move.assert_called_once_with([("/a/b.txt", "/c", "d.txt")])


def test_cli_mv_trailing_slash(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mv", "/a/b.txt", "/c/"])
        assert exit_code == 0
        mock_mgr.list_dir.assert_not_called()
        mock_mgr.batch_move.assert_called_once_with([("/a/b.txt", "/c", "b.txt")])


def test_cli_quota(capsys):
    with patch("bdpan_cli.cli._get_account_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.quota.return_value = {"errno": 0, "total": 3221225472000, "used": 1073741824000}
        mock_client_getter.return_value = mock_client

        exit_code = main(["quota"])
        assert exit_code == 0
        mock_client.quota.assert_called_once_with(check_expire=False, check_free=False)
        captured = capsys.readouterr()
        assert "网盘容量" in captured.out
        assert "3000.00 GB" in captured.out
        assert "1000.00 GB" in captured.out


def test_cli_quota_expire_timestamp_formatted(capsys):
    with patch("bdpan_cli.cli._get_account_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.quota.return_value = {"errno": 0, "total": 100, "used": 0, "expire": 1893456000}
        mock_client_getter.return_value = mock_client

        exit_code = main(["quota", "--check-expire"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "2030-01-01" in captured.out


def test_cli_whoami(capsys):
    with patch("bdpan_cli.cli._get_account_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.user_info.return_value = {
            "errno": 0,
            "baidu_name": "alice",
            "netdisk_name": "alice_net",
            "vip_type": 2,
        }
        mock_client_getter.return_value = mock_client

        exit_code = main(["whoami"])
        assert exit_code == 0
        mock_client.user_info.assert_called_once_with()
        captured = capsys.readouterr()
        assert "alice" in captured.out
        assert "超级会员" in captured.out


def test_cli_search(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.search.return_value = [
            {"path": "/影视/电影/a", "server_filename": "a", "isdir": 1, "size": 0},
            {"path": "/影视/b.mkv", "server_filename": "b.mkv", "isdir": 0, "size": 2048},
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["search", "关键词", "--dir", "/影视"])
        assert exit_code == 0
        mock_mgr.search.assert_called_once_with(
            "关键词", dir_path="/影视", recursion=True, page=1, num=100
        )
        captured = capsys.readouterr()
        assert "/影视/电影/a" in captured.out
        assert "/影视/b.mkv" in captured.out
        assert "2.0 KB" in captured.out


def test_cli_search_empty(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.search.return_value = []
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["search", "不存在"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "未找到" in captured.out


def test_cli_search_full_page_hint(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.search.return_value = [
            {"path": f"/f/{i}", "server_filename": str(i), "isdir": 0, "size": 1}
            for i in range(3)
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["search", "k", "--num", "3"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "--page 2" in captured.out


def test_cli_tree(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.walk.return_value = (
            [
                (0, {"path": "/t/A", "server_filename": "A", "isdir": 1, "size": 0}),
                (1, {"path": "/t/A/c.mkv", "server_filename": "c.mkv", "isdir": 0, "size": 1048576}),
                (0, {"path": "/t/b.txt", "server_filename": "b.txt", "isdir": 0, "size": 10}),
            ],
            [],
        )
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["tree", "/t", "--depth", "2"])
        assert exit_code == 0
        mock_mgr.walk.assert_called_once_with("/t", max_depth=2)
        captured = capsys.readouterr()
        assert "递归 1 个子目录，2 个文件" in captured.out
        assert "c.mkv (1.0 MB)" in captured.out
        assert "b.txt (10 B)" in captured.out


def test_cli_tree_writes_index(tmp_path, capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        entry = {"path": "/t/b.txt", "server_filename": "b.txt", "isdir": 0, "size": 10, "fs_id": 42}
        mock_mgr.walk.return_value = ([(0, entry)], [])
        mock_mgr_getter.return_value = mock_mgr

        index_file = tmp_path / "index.json"
        exit_code = main(["tree", "/t", "--index", str(index_file)])
        assert exit_code == 0

        import json
        payload = json.loads(index_file.read_text(encoding="utf-8"))
        assert payload["version"] == 1
        assert payload["root"] == "/t"
        assert payload["stats"] == {"dirs": 0, "files": 1, "total_size": 10}
        assert payload["errors"] == []
        assert payload["entries"] == [entry]


def test_cli_tree_partial_errors_exit_1(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.walk.return_value = (
            [(0, {"path": "/t/b.txt", "server_filename": "b.txt", "isdir": 0, "size": 1})],
            [("/t/locked", "读取目录失败 [/t/locked]: 31066")],
        )
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["tree", "/t"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "1 个子目录读取失败" in captured.out
        assert "/t/locked" in captured.out


def test_cli_cp_multi_source_into_existing_dir(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [{"path": "/dst", "isdir": 1}]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/a/x", "/b/y", "/dst"])
        assert exit_code == 0
        mock_mgr.batch_copy.assert_called_once_with([("/a/x", "/dst", "x"), ("/b/y", "/dst", "y")])
        mock_mgr.copy.assert_not_called()


def test_cli_mv_multi_source_trailing_slash(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mv", "/a/dir/", "/b/c.mkv", "/dst/"])
        assert exit_code == 0
        # 尾斜杠直接目录语义，不发起 list_dir 探测；源尾斜杠不污染名称
        mock_mgr.list_dir.assert_not_called()
        mock_mgr.batch_move.assert_called_once_with([("/a/dir/", "/dst", "dir"), ("/b/c.mkv", "/dst", "c.mkv")])


def test_cli_mv_multi_source_dest_not_dir_exit_1(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        # 父目录可读但不含 dest → dest 非目录，多源拒绝执行
        mock_mgr.list_dir.return_value = []
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mv", "/a", "/b", "/not-a-dir"])
        assert exit_code == 1
        mock_mgr.batch_move.assert_not_called()
        captured = capsys.readouterr()
        assert "已存在目录" in captured.out


def test_cli_cp_multi_source_dest_parent_unreadable_exit_1(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.side_effect = FileManagerError("读取目录失败 [/nope]: 31066")
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["cp", "/a", "/b", "/nope/dst"])
        assert exit_code == 1
        mock_mgr.batch_copy.assert_not_called()


def test_cli_mv_single_source_unchanged(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [{"path": "/dst", "isdir": 1}]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["mv", "/a/x", "/dst"])
        assert exit_code == 0
        # 单源保持既有双语义：走 _resolve_dest + batch_move 单项通道
        mock_mgr.batch_move.assert_called_once_with([("/a/x", "/dst", "x")])


def _make_local_file(tmp_path, name="f.bin", size=10):
    f = tmp_path / name
    f.write_bytes(b"\x01" * size)
    return str(f)


def test_cli_upload_into_existing_dir(tmp_path, capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter, \
         patch("bdpan_cli.cli.Uploader") as mock_uploader_cls:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [{"path": "/dst", "isdir": 1}]
        mock_mgr_getter.return_value = mock_mgr
        mock_uploader_cls.return_value.upload.return_value = {
            "errno": 0, "path": "/dst/f.bin", "size": 10, "server_filename": "f.bin"
        }

        local = _make_local_file(tmp_path)
        exit_code = main(["upload", local, "/dst"])
        assert exit_code == 0
        mock_uploader_cls.return_value.upload.assert_called_once()
        call_args = mock_uploader_cls.return_value.upload.call_args
        assert call_args[0] == (local, "/dst/f.bin")
        assert call_args[1]["rtype"] == 1
        assert callable(call_args[1]["progress"])
        captured = capsys.readouterr()
        assert "上传成功: /dst/f.bin (10 B)" in captured.out


def test_cli_upload_trailing_slash_no_probe(tmp_path, capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter, \
         patch("bdpan_cli.cli.Uploader") as mock_uploader_cls:
        mock_mgr = MagicMock()
        mock_mgr_getter.return_value = mock_mgr
        mock_uploader_cls.return_value.upload.return_value = {
            "errno": 0, "path": "/dst2/f.bin", "size": 10, "server_filename": "f.bin"
        }

        local = _make_local_file(tmp_path)
        exit_code = main(["upload", local, "/dst2/"])
        assert exit_code == 0
        mock_mgr.list_dir.assert_not_called()
        assert mock_uploader_cls.return_value.upload.call_args[0] == (local, "/dst2/f.bin")


def test_cli_upload_full_target_path(tmp_path):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter, \
         patch("bdpan_cli.cli.Uploader") as mock_uploader_cls:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = []  # dest 不存在 → 目标目录/新名
        mock_mgr_getter.return_value = mock_mgr
        mock_uploader_cls.return_value.upload.return_value = {"errno": 0, "path": "/dst/renamed.bin"}

        local = _make_local_file(tmp_path)
        exit_code = main(["upload", local, "/dst/renamed.bin"])
        assert exit_code == 0
        assert mock_uploader_cls.return_value.upload.call_args[0] == (local, "/dst/renamed.bin")


def test_cli_upload_overwrite_flag(tmp_path):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter, \
         patch("bdpan_cli.cli.Uploader") as mock_uploader_cls:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = []
        mock_mgr_getter.return_value = mock_mgr
        mock_uploader_cls.return_value.upload.return_value = {"errno": 0, "path": "/dst/f.bin"}

        local = _make_local_file(tmp_path)
        exit_code = main(["upload", local, "/dst/f.bin", "--overwrite"])
        assert exit_code == 0
        assert mock_uploader_cls.return_value.upload.call_args[1]["rtype"] == 3


def test_cli_upload_missing_local_file(tmp_path, capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr_getter.return_value = MagicMock()

        exit_code = main(["upload", str(tmp_path / "nope.bin"), "/dst/"])
        assert exit_code == 1
        assert "本地文件不存在" in capsys.readouterr().out


def test_cli_dedup_no_duplicates(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [
            {"server_filename": "single.mkv", "path": "/movies/single.mkv", "isdir": 0, "size": 100}
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["dedup", "/movies"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "未发现任何冲突副本或重复条目" in captured.out


def test_cli_dedup_dry_run(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [
            {"server_filename": "film.mkv", "path": "/movies/film.mkv", "isdir": 0, "size": 1000},
            {"server_filename": "film (1).mkv", "path": "/movies/film (1).mkv", "isdir": 0, "size": 1000},
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["dedup", "/movies", "--dry-run"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "发现 1 个冲突与重复条目" in captured.out
        assert "film (1).mkv" in captured.out
        assert "--dry-run 预演模式" in captured.out
        mock_mgr.batch_move.assert_not_called()
        mock_mgr.batch_delete.assert_not_called()


def test_cli_dedup_staging_with_yes(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [
            {"server_filename": "film.mkv", "path": "/movies/film.mkv", "isdir": 0, "size": 1000},
            {"server_filename": "film (1).mkv", "path": "/movies/film (1).mkv", "isdir": 0, "size": 1000},
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["dedup", "/movies", "--staging-dir", "/movies/pending_delete", "-y"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "已成功将 1 项移入隔离目录: /movies/pending_delete" in captured.out
        mock_mgr.batch_move.assert_called_once_with(
            [("/movies/film (1).mkv", "/movies/pending_delete", "film (1).mkv")],
            batch_size=50,
        )


def test_cli_dedup_delete_with_yes(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.list_dir.return_value = [
            {"server_filename": "film.mkv", "path": "/movies/film.mkv", "isdir": 0, "size": 1000},
            {"server_filename": "film (1).mkv", "path": "/movies/film (1).mkv", "isdir": 0, "size": 1000},
        ]
        mock_mgr_getter.return_value = mock_mgr

        exit_code = main(["dedup", "/movies", "--delete", "-y"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "已成功从网盘删除 1 项（已移入回收站）" in captured.out
        mock_mgr.batch_delete.assert_called_once_with(["/movies/film (1).mkv"], batch_size=50)


def test_cli_dedup_same_dir_error(capsys):
    with patch("bdpan_cli.cli._get_file_manager") as mock_mgr_getter:
        mock_mgr_getter.return_value = MagicMock()

        exit_code = main(["dedup", "/movies", "--staging-dir", "/movies"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "隔离目录不能与待扫描目录相同" in captured.out

