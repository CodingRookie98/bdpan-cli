"""Unit tests for organize module."""

from unittest.mock import MagicMock, patch

from bdpan_cli.organize import run_organization


@patch("bdpan_cli.organize.load_config")
@patch("bdpan_cli.organize.TokenManager")
@patch("bdpan_cli.organize.FileManager")
def test_run_organization_flow(mock_mgr_cls, mock_token_cls, mock_config):
    mock_mgr = MagicMock()
    mock_mgr_cls.return_value = mock_mgr

    # 模拟 list_dir 阶段 0 返回
    mock_mgr.list_dir.side_effect = [
        # 阶段 0: 检查
        [
            {"server_filename": "0_notWatch", "isdir": 1, "path": "/影视/电影/0_notWatch"},
            {"server_filename": "movie1", "isdir": 1, "path": "/影视/电影/movie1"},
            {"server_filename": "film.torrent", "isdir": 0, "path": "/影视/电影/film.torrent"},
        ],
        # 阶段 3: 扫描待归类条目
        [
            {"server_filename": "unwatched", "isdir": 1, "path": "/影视/电影/unwatched"},
            {"server_filename": "watched", "isdir": 1, "path": "/影视/电影/watched"},
            {"server_filename": "pending_triage", "isdir": 1, "path": "/影视/电影/pending_triage"},
            {"server_filename": "movie1", "isdir": 1, "path": "/影视/电影/movie1"},
            {"server_filename": "film.torrent", "isdir": 0, "path": "/影视/电影/film.torrent"},
        ],
        # 阶段 4: 对账 final_root
        [
            {"server_filename": "unwatched", "isdir": 1},
            {"server_filename": "watched", "isdir": 1},
            {"server_filename": "pending_triage", "isdir": 1},
        ],
        # 对账 watched
        [{"server_filename": "movie1", "isdir": 1}],
        # 对账 triage
        [{"server_filename": "film.torrent", "isdir": 0}],
        # 对账 unwatched
        [],
    ]

    run_organization()

    # 验证 rename 0_notWatch -> unwatched
    mock_mgr.rename.assert_called_once_with("/影视/电影/0_notWatch", "unwatched")

    # 验证 mkdir
    assert mock_mgr.mkdir.call_count == 2

    # 验证 batch_move 两次：一次 triage，一次 watched
    assert mock_mgr.batch_move.call_count == 2
    first_call_args = mock_mgr.batch_move.call_args_list[0][0][0]
    assert first_call_args == [("/影视/电影/film.torrent", "/影视/电影/pending_triage", "film.torrent")]

    second_call_args = mock_mgr.batch_move.call_args_list[1][0][0]
    assert second_call_args == [("/影视/电影/movie1", "/影视/电影/watched", "movie1")]
