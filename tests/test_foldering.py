from unittest.mock import MagicMock
from bdpan_cli.foldering import plan_foldering, execute_foldering
from bdpan_cli.scraper import MovieMetadata


def test_plan_foldering():
    mock_mgr = MagicMock()
    mock_mgr.list_dir.side_effect = lambda path: [
        {"server_filename": "some_folder", "isdir": 1, "size": 0},
        {"server_filename": "non_media.txt", "isdir": 0, "size": 10},
        {"server_filename": "The.Matrix.1999.1080p.mkv", "isdir": 0, "size": 1000},
        {"server_filename": "The.Matrix.1999.720p.mp4", "isdir": 0, "size": 500},
    ] if path == "/影视/电影/test" else []

    mock_scraper = MagicMock()
    mock_scraper.scrape_folder_name.return_value = MovieMetadata(
        title="黑客帝国",
        original_title="The Matrix",
        year="1999",
        imdb_id="tt0133093",
    )

    plan = plan_foldering("/影视/电影/test", mock_mgr, mock_scraper)

    assert len(plan) == 1
    item = plan[0]
    assert item["target_folder_name"] == "黑客帝国.The.Matrix.1999.tt0133093"
    assert len(item["files"]) == 2
    filenames = [f["filename"] for f in item["files"]]
    assert "The.Matrix.1999.1080p.mkv" in filenames
    assert "The.Matrix.1999.720p.mp4" in filenames


def test_execute_foldering():
    mock_mgr = MagicMock()
    plan = [
        {
            "target_folder_name": "黑客帝国.The.Matrix.1999.tt0133093",
            "target_folder_path": "/影视/电影/test/黑客帝国.The.Matrix.1999.tt0133093",
            "files": [
                {"filename": "The.Matrix.1999.1080p.mkv", "path": "/影视/电影/test/The.Matrix.1999.1080p.mkv"},
            ],
        }
    ]

    res = execute_foldering("/影视/电影/test", plan, mock_mgr)
    assert res["folders_created"] == 1
    assert res["files_moved"] == 1
    mock_mgr.mkdir.assert_called_once_with("/影视/电影/test/黑客帝国.The.Matrix.1999.tt0133093")
    mock_mgr.batch_move.assert_called_once_with(
        [("/影视/电影/test/The.Matrix.1999.1080p.mkv", "/影视/电影/test/黑客帝国.The.Matrix.1999.tt0133093", "The.Matrix.1999.1080p.mkv")],
        batch_size=25,
    )


def test_plan_foldering_with_nested_subdirectories():
    mock_mgr = MagicMock()
    # 顶层包含一个非规范子目录和一个已规范目录
    mock_mgr.list_dir.side_effect = [
        [
            {"server_filename": "黑客帝国.The.Matrix.1999.tt0133093", "path": "/test/黑客帝国.The.Matrix.1999.tt0133093", "isdir": 1},
            {"server_filename": "01 玩具总动员 (1995) 4K", "path": "/test/01 玩具总动员 (1995) 4K", "isdir": 1},
        ],
        # 扫描 01 玩具总动员 (1995) 4K 的子项
        [
            {"server_filename": "Toy.Story.1995.2160p.mkv", "path": "/test/01 玩具总动员 (1995) 4K/Toy.Story.1995.2160p.mkv", "isdir": 0, "size": 16000000},
            {"server_filename": "Toy.Story.srt", "path": "/test/01 玩具总动员 (1995) 4K/Toy.Story.srt", "isdir": 0, "size": 20000},
            {"server_filename": "sample.nfo", "path": "/test/01 玩具总动员 (1995) 4K/sample.nfo", "isdir": 0, "size": 500},
        ],
    ]

    mock_scraper = MagicMock()
    mock_scraper.scrape_folder_name.return_value = MovieMetadata(
        title="玩具总动员",
        original_title="Toy Story",
        year="1995",
        imdb_id="tt0114709",
    )

    plan = plan_foldering("/test", mock_mgr, mock_scraper)

    assert len(plan) == 1
    item = plan[0]
    assert item["target_folder_name"] == "玩具总动员.Toy.Story.1995.tt0114709"
    # 应包含 mkv 与 srt 字幕，过滤掉 nfo
    assert len(item["files"]) == 2
    fnames = [f["filename"] for f in item["files"]]
    assert "Toy.Story.1995.2160p.mkv" in fnames
    assert "Toy.Story.srt" in fnames

