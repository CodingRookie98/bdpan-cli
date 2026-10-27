from unittest.mock import MagicMock
import pytest

from bdpan_cli.dedup import (
    CONFLICT_SUFFIX_PATTERN,
    DedupCandidate,
    DedupPlan,
    execute_dedup,
    plan_dedup,
    scan_directory_duplicates,
)
from bdpan_cli.file_manager import FileManagerError


def test_conflict_suffix_pattern():
    # 正常冲突匹配
    m1 = CONFLICT_SUFFIX_PATTERN.match("01 玩具总动员 (1)")
    assert m1 is not None
    assert m1.group("base") == "01 玩具总动员"
    assert m1.group("index") == "1"
    assert m1.group("ext") is None

    m2 = CONFLICT_SUFFIX_PATTERN.match("Toy.Story(2).mp4")
    assert m2 is not None
    assert m2.group("base") == "Toy.Story"
    assert m2.group("index") == "2"
    assert m2.group("ext") == ".mp4"

    m3 = CONFLICT_SUFFIX_PATTERN.match("movie_ (01).mkv")
    assert m3 is not None
    assert m3.group("base").rstrip(" ._-") == "movie"
    assert m3.group("index") == "01"
    assert m3.group("ext") == ".mkv"

    # 4 位年份不匹配（天然防御）
    m_year = CONFLICT_SUFFIX_PATTERN.match("Blade Runner (1982).mkv")
    assert m_year is None

    # 无括号不匹配
    m_normal = CONFLICT_SUFFIX_PATTERN.match("Toy Story.mkv")
    assert m_normal is None


def test_scan_directory_duplicates_with_primary():
    entries = [
        {"server_filename": "Toy Story", "path": "/movies/Toy Story", "isdir": 1, "size": 0},
        {"server_filename": "Toy Story (1)", "path": "/movies/Toy Story (1)", "isdir": 1, "size": 0},
        {"server_filename": "film.mkv", "path": "/movies/film.mkv", "isdir": 0, "size": 1000},
        {"server_filename": "film (1).mkv", "path": "/movies/film (1).mkv", "isdir": 0, "size": 1000},
        {"server_filename": "film (2).mkv", "path": "/movies/film (2).mkv", "isdir": 0, "size": 2000},
    ]

    candidates, orphan_count = scan_directory_duplicates("/movies", entries)
    assert orphan_count == 0
    assert len(candidates) == 3

    cand_map = {c.name: c for c in candidates}
    assert "Toy Story" not in cand_map
    assert "film.mkv" not in cand_map

    # 目录副本
    c_dir = cand_map["Toy Story (1)"]
    assert c_dir.isdir is True
    assert "存在同名主目录 'Toy Story'" in c_dir.reason
    assert c_dir.primary_path == "/movies/Toy Story"

    # 大小一致的文件副本
    c_f1 = cand_map["film (1).mkv"]
    assert c_f1.isdir is False
    assert "且大小一致" in c_f1.reason
    assert c_f1.primary_path == "/movies/film.mkv"

    # 大小不同的文件副本
    c_f2 = cand_map["film (2).mkv"]
    assert c_f2.isdir is False
    assert "序号冲突副本 (2)" in c_f2.reason
    assert c_f2.primary_path == "/movies/film.mkv"


def test_scan_directory_duplicates_orphans():
    # 只有 (1) 和 (2)，没有原版
    entries = [
        {"server_filename": "video (1).mkv", "path": "/movies/video (1).mkv", "isdir": 0, "size": 1000},
        {"server_filename": "video (2).mkv", "path": "/movies/video (2).mkv", "isdir": 0, "size": 1000},
    ]

    # 默认不治理无主孤儿组
    cand_default, orph_default = scan_directory_duplicates("/movies", entries, include_orphans=False)
    assert orph_default == 1
    assert len(cand_default) == 0

    # 开启 include_orphans 后保留 (1)，清理 (2)
    cand_orph, orph_cnt = scan_directory_duplicates("/movies", entries, include_orphans=True)
    assert orph_cnt == 1
    assert len(cand_orph) == 1
    assert cand_orph[0].name == "video (2).mkv"
    assert "保留最低序号 'video (1).mkv'" in cand_orph[0].reason


def test_scan_directory_duplicates_empty_dir():
    entries = [
        {"server_filename": "empty_folder", "path": "/movies/empty_folder", "isdir": 1, "size": 0},
    ]
    mock_mgr = MagicMock()
    mock_mgr.list_dir.return_value = []

    cand, _ = scan_directory_duplicates("/movies", entries, include_empty=True, mgr=mock_mgr)
    assert len(cand) == 1
    assert cand[0].name == "empty_folder"
    assert cand[0].isdir is True
    assert "空目录 (0 项)" in cand[0].reason


def test_plan_dedup_non_recursive():
    mock_mgr = MagicMock()
    mock_mgr.list_dir.return_value = [
        {"server_filename": "a.mp4", "path": "/v/a.mp4", "isdir": 0, "size": 500},
        {"server_filename": "a (1).mp4", "path": "/v/a (1).mp4", "isdir": 0, "size": 500},
    ]

    plan = plan_dedup("/v", mock_mgr, recursive=False)
    assert plan.target_dir == "/v"
    assert plan.scanned_count == 2
    assert len(plan.candidates) == 1
    assert plan.total_size == 500
    assert plan.candidates[0].name == "a (1).mp4"


def test_plan_dedup_recursive():
    mock_mgr = MagicMock()
    mock_mgr.walk.return_value = (
        [
            (0, {"server_filename": "sub1", "path": "/v/sub1", "isdir": 1, "size": 0}),
            (1, {"server_filename": "m.mkv", "path": "/v/sub1/m.mkv", "isdir": 0, "size": 2000}),
            (1, {"server_filename": "m (1).mkv", "path": "/v/sub1/m (1).mkv", "isdir": 0, "size": 2000}),
        ],
        [],
    )

    plan = plan_dedup("/v", mock_mgr, recursive=True)
    assert plan.target_dir == "/v"
    assert len(plan.candidates) == 1
    assert plan.candidates[0].path == "/v/sub1/m (1).mkv"
    assert plan.total_size == 2000


def test_execute_dedup_staging():
    mock_mgr = MagicMock()
    plan = DedupPlan(
        target_dir="/movies",
        candidates=[
            DedupCandidate(
                path="/movies/a (1).mkv",
                name="a (1).mkv",
                isdir=False,
                size=1000,
                reason="conflict",
                clean_name="a.mkv",
            )
        ],
        total_size=1000,
        scanned_count=2,
    )

    res = execute_dedup(plan, mock_mgr, staging_dir="/movies/pending_delete")
    assert res == {"moved": 1, "deleted": 0}
    mock_mgr.mkdir.assert_called_once_with("/movies/pending_delete")
    mock_mgr.batch_move.assert_called_once_with(
        [("/movies/a (1).mkv", "/movies/pending_delete", "a (1).mkv")],
        batch_size=50,
    )


def test_execute_dedup_delete():
    mock_mgr = MagicMock()
    plan = DedupPlan(
        target_dir="/movies",
        candidates=[
            DedupCandidate(
                path="/movies/del (1)",
                name="del (1)",
                isdir=True,
                size=0,
                reason="conflict",
                clean_name="del",
            )
        ],
        total_size=0,
        scanned_count=2,
    )

    res = execute_dedup(plan, mock_mgr, delete=True)
    assert res == {"moved": 0, "deleted": 1}
    mock_mgr.batch_delete.assert_called_once_with(["/movies/del (1)"], batch_size=50)


def test_execute_dedup_empty_candidates():
    mock_mgr = MagicMock()
    plan = DedupPlan(target_dir="/m", candidates=[], total_size=0, scanned_count=0)
    res = execute_dedup(plan, mock_mgr, staging_dir="/p")
    assert res == {"moved": 0, "deleted": 0}
    mock_mgr.batch_move.assert_not_called()
    mock_mgr.batch_delete.assert_not_called()
