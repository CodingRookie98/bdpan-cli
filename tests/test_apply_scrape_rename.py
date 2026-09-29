"""Unit tests for apply_scrape_rename."""

import json
from unittest.mock import MagicMock, patch

from bd_net_disc_mgr.apply_scrape_rename import apply_renames


@patch("bd_net_disc_mgr.apply_scrape_rename.load_config")
@patch("bd_net_disc_mgr.apply_scrape_rename.TokenManager")
@patch("bd_net_disc_mgr.apply_scrape_rename.FileManager")
def test_apply_renames_flow(mock_mgr_cls, mock_token_cls, mock_config, tmp_path):
    mock_mgr = MagicMock()
    mock_mgr_cls.return_value = mock_mgr
    mock_mgr.batch_rename.return_value = [{"errno": 0, "info": [{"errno": 0}]}]
    mock_mgr.list_dir.return_value = [{"server_filename": "Old.Movie.2020", "path": "/影视/电影/unwatched/Old.Movie.2020"}]


    # 创建虚拟 preview.json
    preview_file = tmp_path / "test_preview.json"
    data = [
        {"index": 1, "raw_name": "Old.Movie.2020", "target_name": "老电影.Old.Movie.2020.tt1234567", "status": "OK"},
        {"index": 2, "raw_name": "Already.Clean.2021.tt7654321", "target_name": "Already.Clean.2021.tt7654321", "status": "OK"},
        {"index": 3, "raw_name": "Failed.Movie", "target_name": "【未匹配到】", "status": "FAIL"},
    ]
    preview_file.write_text(json.dumps(data), encoding="utf-8")

    apply_renames(str(preview_file))

    # 只有第 1 个执行 batch_rename，第 2 个相同跳过，第 3 个失败跳过
    mock_mgr.batch_rename.assert_called_once_with(
        [("/影视/电影/unwatched/Old.Movie.2020", "老电影.Old.Movie.2020.tt1234567")],
        batch_size=50,
    )
