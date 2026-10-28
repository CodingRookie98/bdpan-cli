"""Unit tests for OperationLogger and UndoEngine (BK-0034)."""

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from bdpan_cli.ops import OperationLogger, UndoEngine, UndoError


def test_record_and_get_operation(tmp_path):
    logger = OperationLogger(ops_dir=tmp_path)
    items = [
        {"src": "/movies/old.mp4", "dest": "/movies/new.mp4"},
        {"src": "/movies/film.mkv", "dest": "/archive/film.mkv"},
    ]
    op_id = logger.record_operation(command="rename", items=items, account="default")
    assert op_id is not None
    assert (tmp_path / f"{op_id}.json").exists()

    op = logger.get_operation(op_id)
    assert op is not None
    assert op["op_id"] == op_id
    assert op["command"] == "rename"
    assert op["account"] == "default"
    assert len(op["items"]) == 2
    assert op["undone"] is False


def test_list_operations(tmp_path):
    logger = OperationLogger(ops_dir=tmp_path)
    logger.record_operation("mv", [{"src": "/a", "dest": "/b"}])
    logger.record_operation("rename", [{"src": "/c", "dest": "/d"}])

    ops = logger.list_operations()
    assert len(ops) == 2
    # 倒序排列（最新的在前面）
    assert ops[0]["command"] == "rename"
    assert ops[1]["command"] == "mv"


def test_undo_engine_plan(tmp_path):
    logger = OperationLogger(ops_dir=tmp_path)
    items = [
        {"src": "/videos/unwatched/movie.mp4", "dest": "/videos/watched/movie.mp4"},
    ]
    op_id = logger.record_operation(command="mv", items=items)

    mock_mgr = MagicMock()
    engine = UndoEngine(mock_mgr, ops_logger=logger)
    plan = engine.plan_undo(op_id)

    assert plan["op_id"] == op_id
    assert len(plan["reversals"]) == 1
    # 逆向对：原来的 dest 变成 src，原来的 src 变成目标
    rev = plan["reversals"][0]
    assert rev["src"] == "/videos/watched/movie.mp4"
    assert rev["dest_dir"] == "/videos/unwatched"
    assert rev["newname"] == "movie.mp4"


def test_undo_engine_execute_success(tmp_path):
    logger = OperationLogger(ops_dir=tmp_path)
    items = [
        {"src": "/movies/origin.mp4", "dest": "/archive/origin.mp4"},
    ]
    op_id = logger.record_operation(command="mv", items=items)

    mock_mgr = MagicMock()
    mock_mgr.batch_move.return_value = {"errno": 0}

    engine = UndoEngine(mock_mgr, ops_logger=logger)
    res = engine.execute_undo(op_id, dry_run=False)

    assert res["undone_count"] == 1
    mock_mgr.batch_move.assert_called_once()
    # 验证流水状态被更新为已撤销
    op = logger.get_operation(op_id)
    assert op["undone"] is True


def test_undo_already_undone_error(tmp_path):
    logger = OperationLogger(ops_dir=tmp_path)
    items = [{"src": "/a", "dest": "/b"}]
    op_id = logger.record_operation(command="mv", items=items)

    mock_mgr = MagicMock()
    mock_mgr.batch_move.return_value = {"errno": 0}

    engine = UndoEngine(mock_mgr, ops_logger=logger)
    engine.execute_undo(op_id, dry_run=False)

    # 再次撤销应该报错
    with pytest.raises(UndoError) as exc_info:
        engine.execute_undo(op_id, dry_run=False)
    assert "已被撤销" in str(exc_info.value)
