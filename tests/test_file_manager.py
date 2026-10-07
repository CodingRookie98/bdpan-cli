"""Unit tests for FileManager."""

import json
from unittest.mock import MagicMock

import pytest

from bdpan_cli.file_manager import FileManager, FileManagerError
from openapi_client.rest import ApiException


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


def test_rename_partial_item_failure():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    # 顶层 errno=0 但 info[].errno != 0 → 逐项校验兜底报错
    mgr._filemanager_api.filemanagerrename.return_value = {
        "errno": 0,
        "info": [{"errno": 0, "path": "/a", "to_path": "/b"}],
    }
    assert mgr.rename("/a", "b").get("errno") == 0

    mgr._filemanager_api.filemanagerrename.return_value = {
        "errno": 0,
        "info": [{"errno": -6, "path": "/a", "to_path": "/b"}],
    }
    with pytest.raises(FileManagerError, match="重命名返回错误 \\[/a -> b\\]: 第 1 项失败 errno=-6"):
        mgr.rename("/a", "b")


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


def test_batch_move_partial_item_failure():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    # 批内 2 项，第 2 项服务端失败但顶层 errno=0 → 逐项校验兜底
    mgr._filemanager_api.filemanagermove.return_value = {
        "errno": 0,
        "info": [
            {"errno": 0, "from": "/src/a", "to": "/dest/a"},
            {"errno": 12, "from": "/src/b", "to": "/dest/b"},
        ],
    }

    with pytest.raises(FileManagerError, match="批量移动批次 1 返回错误: 第 2 项失败 errno=12"):
        mgr.batch_move([("/src/a", "/dest", "a"), ("/src/b", "/dest", "b")])


def test_copy_success():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagercopy.return_value = {"errno": 0}

    res = mgr.copy("/src/movie", "/dst", "movie")
    assert res.get("errno") == 0
    mgr._filemanager_api.filemanagercopy.assert_called_once()
    call_args = mgr._filemanager_api.filemanagercopy.call_args[1]
    assert call_args["access_token"] == "fake-token"
    assert call_args["_async"] == 0
    payload = json.loads(call_args["filelist"])
    assert payload == [{"path": "/src/movie", "dest": "/dst", "newname": "movie"}]


def test_copy_error_single_item_wording():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagercopy.return_value = {"errno": 12, "errmsg": "cannot copy"}

    # 单项复制的错误文案不携带"批量复制批次"字样
    with pytest.raises(FileManagerError) as exc_info:
        mgr.copy("/src/movie", "/dst", "movie")
    assert "复制返回错误 [/src/movie -> /dst/movie]" in str(exc_info.value)
    assert "批量复制" not in str(exc_info.value)


def test_copy_api_error_single_item_wording():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagercopy.side_effect = ApiException(status=403, reason="Forbidden")

    with pytest.raises(FileManagerError) as exc_info:
        mgr.copy("/src/movie", "/dst", "movie")
    assert "复制 [/src/movie -> /dst/movie]失败: 403" in str(exc_info.value)
    assert "批量复制" not in str(exc_info.value)


def test_batch_copy_error_keeps_batch_wording():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagercopy.return_value = {"errno": 12, "errmsg": "cannot copy"}

    # 真批量场景保留"批量复制批次 N"文案
    with pytest.raises(FileManagerError, match="批量复制批次 1 返回错误"):
        mgr.batch_copy([("/src/movie", "/dst", "movie")])


def test_copy_partial_item_failure():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    # 顶层 errno=0 但条目失败 → 必须报错，不能漏报
    mgr._filemanager_api.filemanagercopy.return_value = {
        "errno": 0,
        "info": [{"errno": 12, "from": "/src/movie", "to": "/dst/movie"}],
    }

    with pytest.raises(FileManagerError, match="第 1 项失败 errno=12"):
        mgr.copy("/src/movie", "/dst", "movie")


def test_batch_copy_batches():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    mgr._filemanager_api.filemanagercopy.return_value = {"errno": 0, "info": []}

    items = [
        (f"/src/file_{i}", "/dest", f"file_{i}")
        for i in range(105)
    ]
    results = mgr.batch_copy(items, batch_size=50)

    # 105 个元素，每次 50 个，应当调用 3 次
    assert mgr._filemanager_api.filemanagercopy.call_count == 3
    assert len(results) == 3

    first_call_filelist = json.loads(mgr._filemanager_api.filemanagercopy.call_args_list[0][1]["filelist"])
    assert len(first_call_filelist) == 50
    assert first_call_filelist[0] == {"path": "/src/file_0", "dest": "/dest", "newname": "file_0"}

    third_call_filelist = json.loads(mgr._filemanager_api.filemanagercopy.call_args_list[2][1]["filelist"])
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


def test_delete_partial_item_failure():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    # 顶层 errno=0 但 info[].errno != 0 → 逐项校验兜底报错
    mgr._filemanager_api.filemanagerdelete.return_value = {
        "errno": 0,
        "info": [{"errno": -9, "path": "/test/path"}],
    }

    with pytest.raises(FileManagerError, match="删除返回错误 \\[/test/path\\]: 第 1 项失败 errno=-9"):
        mgr.delete("/test/path")


def test_delete_success_without_info():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._filemanager_api = MagicMock()
    # 无 info 字段的纯顶层成功响应应正常通过
    mgr._filemanager_api.filemanagerdelete.return_value = {"errno": 0, "request_id": 123}

    res = mgr.delete("/test/path")
    assert res.get("errno") == 0



def test_search_forwards_params():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._fileinfo_api = MagicMock()
    mgr._fileinfo_api.xpanfilesearch.return_value = {
        "list": [{"path": "/a/b.mkv", "server_filename": "b.mkv", "size": 1, "isdir": 0}]
    }

    res = mgr.search("movie", dir_path="/a", recursion=True, page=2, num=50)
    assert len(res) == 1
    mgr._fileinfo_api.xpanfilesearch.assert_called_once_with(
        access_token="fake-token",
        key="movie",
        web="1",
        num="50",
        page="2",
        recursion="1",
        dir="/a",
    )


def test_search_without_dir_omits_dir_param():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._fileinfo_api = MagicMock()
    mgr._fileinfo_api.xpanfilesearch.return_value = {"list": []}

    res = mgr.search("movie")
    assert res == []
    call_kwargs = mgr._fileinfo_api.xpanfilesearch.call_args[1]
    assert "dir" not in call_kwargs
    assert call_kwargs["recursion"] == "1"


def test_search_no_recursion():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._fileinfo_api = MagicMock()
    mgr._fileinfo_api.xpanfilesearch.return_value = {"list": []}

    mgr.search("k", dir_path="/d", recursion=False)
    call_kwargs = mgr._fileinfo_api.xpanfilesearch.call_args[1]
    assert call_kwargs["recursion"] == "0"
    assert call_kwargs["dir"] == "/d"


def test_search_http_error_wrapped():
    mock_client = MagicMock()
    mgr = FileManager("fake-token", mock_client)
    mgr._fileinfo_api = MagicMock()
    mgr._fileinfo_api.xpanfilesearch.side_effect = ApiException(status=400, reason="Bad Request")

    with pytest.raises(FileManagerError, match="搜索失败"):
        mgr.search("k")
