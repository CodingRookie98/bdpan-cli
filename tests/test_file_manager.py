"""Unit tests for FileManager."""

import json
from unittest.mock import MagicMock

import pytest

from bdpan_cli.file_manager import FileManager, FileManagerError


def test_list_dir_pagination():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._fileinfo_api = MagicMock()

    # 模拟分页：第一页 2 条，第二页 1 条，第三页空
    mgr._fileinfo_api.xpanfilelist.side_effect = [
        {"list": [{"server_filename": "a"}, {"server_filename": "b"}]},
        {"list": [{"server_filename": "c"}]},
        {"list": []},
    ]

    res = mgr.list_dir("/test", limit=2)
    assert len(res) == 3
    assert [x["server_filename"] for x in res] == ["a", "b", "c"]
    assert mgr._fileinfo_api.xpanfilelist.call_count == 2


def test_mkdir_success():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._fileupload_api = MagicMock()
    mgr._fileupload_api.xpanfilecreate.return_value = {"errno": 0, "path": "/test"}

    res = mgr.mkdir("/test")
    assert res.get("errno") == 0
    mgr._fileupload_api.xpanfilecreate.assert_called_once_with(
        access_token="fake-token",
        path="/test",
        isdir=1,
        size=0,
        uploadid="",
        block_list="[]",
        rtype=1,
    )


def test_mkdir_already_exists():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._fileupload_api = MagicMock()
    mgr._fileupload_api.xpanfilecreate.return_value = {"errno": -8, "errmsg": "file already exists"}

    res = mgr.mkdir("/test")
    assert res.get("errno") == -8


def test_rename_success():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagerrename.return_value = {
        "errno": 0,
        "info": [{"errno": 0, "path": "/test/old", "to_path": "/test/new"}],
    }

    res = mgr.rename("/test/old", "new")
    assert res.get("errno") == 0
    mgr._filemanager_api.filemanagerrename.assert_called_once()
    call_args = mgr._filemanager_api.filemanagerrename.call_args[1]
    assert call_args["access_token"] == "fake-token"
    assert call_args["_async"] == 0
    payload = json.loads(call_args["filelist"])
    assert payload == [{"path": "/test/old", "newname": "new"}]


def test_rename_error():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagerrename.return_value = {"errno": 12, "errmsg": "cannot rename"}

    with pytest.raises(FileManagerError, match="重命名返回错误"):
        mgr.rename("/test/old", "new")


def test_batch_move_batches():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagermove.return_value = {"errno": 0, "info": []}

    items = [
        (f"/src/file_{i}", "/dest", f"file_{i}")
        for i in range(105)
    ]
    results = mgr.batch_move(items, batch_size=50)

    # 105 个元素，每次 50 个，应当调用 3 次
    assert mgr._filemanager_api.filemanagermove.call_count == 3
    assert len(results) == 3

    first_call_filelist = json.loads(mgr._filemanager_api.filemanagermove.call_args_list[0][1]["filelist"])
    assert len(first_call_filelist) == 50
    assert first_call_filelist[0] == {"path": "/src/file_0", "dest": "/dest", "newname": "file_0"}

    third_call_filelist = json.loads(mgr._filemanager_api.filemanagermove.call_args_list[2][1]["filelist"])
    assert len(third_call_filelist) == 5


def test_delete():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagerdelete.return_value = {"errno": 0}

    res = mgr.delete("/test/path")
    assert res["errno"] == 0
    call_args = mgr._filemanager_api.filemanagerdelete.call_args[1]
    assert call_args["access_token"] == "fake-token"
    assert call_args["filelist"] == '["/test/path"]'


def test_delete_error():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagerdelete.return_value = {"errno": -9, "errmsg": "file not found"}

    with pytest.raises(FileManagerError, match="删除返回错误"):
        mgr.delete("/test/path")

