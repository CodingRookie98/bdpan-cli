"""Unit tests for Uploader (分片上传与断点续传)."""

import hashlib
import json
import os
from unittest.mock import MagicMock

import pytest
from openapi_client.rest import ApiException

from bdpan_cli.uploader import CHUNK_SIZE, UploadError, Uploader


def _make_uploader() -> tuple[Uploader, MagicMock]:
    mock_client = MagicMock()
    uploader = Uploader("fake-token", mock_client)
    uploader._fileupload_api = MagicMock()
    return uploader, uploader._fileupload_api


# ---------------------------------------------------------------------------
# 分片规划与哈希
# ---------------------------------------------------------------------------


def test_plan_chunks_small_file_single_chunk():
    assert Uploader._plan_chunks(1024) == [(0, 1024)]
    assert Uploader._plan_chunks(CHUNK_SIZE) == [(0, CHUNK_SIZE)]


def test_plan_chunks_multi_chunk_boundary():
    # 4MB + 4MB + 1MB：非末片必须足 4MB（官方 31299 约束）
    chunks = Uploader._plan_chunks(CHUNK_SIZE * 2 + 1)
    assert chunks == [(0, CHUNK_SIZE), (CHUNK_SIZE, CHUNK_SIZE), (CHUNK_SIZE * 2, 1)]


def test_hash_file_chunk_md5s(tmp_path):
    payload = os.urandom(CHUNK_SIZE) + b"B" * 100
    f = tmp_path / "blob.bin"
    f.write_bytes(payload)
    chunks = Uploader._plan_chunks(len(payload))

    md5s = Uploader._hash_file(str(f), chunks)
    assert md5s == [
        hashlib.md5(payload[:CHUNK_SIZE]).hexdigest(),
        hashlib.md5(payload[CHUNK_SIZE:]).hexdigest(),
    ]
    assert all(len(m) == 32 and m == m.lower() for m in md5s)


# ---------------------------------------------------------------------------
# 三阶段流程
# ---------------------------------------------------------------------------


def test_upload_small_file_full_flow(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello bdpan")
    content_md5 = hashlib.md5(b"hello bdpan").hexdigest()

    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U1", "block_list": [0]}
    api.pcssuperfile2.return_value = {"md5": content_md5}
    api.xpanfilecreate.return_value = {"errno": 0, "path": "/dst/hello.txt", "size": 11}

    res = uploader.upload(str(f), "/dst/hello.txt")
    assert res["errno"] == 0

    pre_args = api.xpanfileprecreate.call_args[1]
    assert pre_args["access_token"] == "fake-token"
    assert pre_args["path"] == "/dst/hello.txt"
    assert pre_args["size"] == 11
    assert pre_args["isdir"] == 0
    assert pre_args["autoinit"] == 1
    assert pre_args["rtype"] == 1
    assert json.loads(pre_args["block_list"]) == [content_md5]

    up_args = api.pcssuperfile2.call_args[1]
    assert up_args["type"] == "tmpfile"
    assert up_args["uploadid"] == "U1"
    assert up_args["path"] == "/dst/hello.txt"
    assert up_args["partseq"] == "0"
    # SDK 多部件序列化要求带 .name 的 IOBase，内部以 _NamedBytesIO 承载分片
    from bdpan_cli.uploader import _NamedBytesIO
    assert isinstance(up_args["file"], _NamedBytesIO)
    assert up_args["file"].getvalue() == b"hello bdpan"

    create_args = api.xpanfilecreate.call_args[1]
    assert create_args["uploadid"] == "U1"
    assert create_args["size"] == 11
    assert json.loads(create_args["block_list"]) == [content_md5]


def test_upload_resume_only_missing_chunks(tmp_path):
    uploader, api = _make_uploader()
    payload = os.urandom(CHUNK_SIZE * 2)  # 2 片
    f = tmp_path / "big.bin"
    f.write_bytes(payload)

    # 断点续传：服务端已存在分片 0，只缺分片 1
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U2", "block_list": [1]}
    api.pcssuperfile2.return_value = {"md5": "x"}
    api.xpanfilecreate.return_value = {"errno": 0, "path": "/dst/big.bin"}

    uploader.upload(str(f), "/dst/big.bin")

    seqs = [c[1]["partseq"] for c in api.pcssuperfile2.call_args_list]
    assert seqs == ["1"]  # 仅补传缺失分片
    create_args = api.xpanfilecreate.call_args[1]
    assert json.loads(create_args["block_list"]) == [
        hashlib.md5(payload[:CHUNK_SIZE]).hexdigest(),
        hashlib.md5(payload[CHUNK_SIZE:]).hexdigest(),
    ]


def test_upload_all_chunks_present_skips_superfile(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "done.txt"
    f.write_bytes(b"already there")

    # 秒传/续传完成形态：无缺片 → 直接创建，不发任何分片请求
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U3", "block_list": []}
    api.xpanfilecreate.return_value = {"errno": 0, "path": "/dst/done.txt"}

    uploader.upload(str(f), "/dst/done.txt")
    api.pcssuperfile2.assert_not_called()
    api.xpanfilecreate.assert_called_once()


def test_upload_precreate_errno_raises(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "x.txt"
    f.write_bytes(b"x")
    api.xpanfileprecreate.return_value = {"errno": -10}

    with pytest.raises(UploadError, match="errno=-10"):
        uploader.upload(str(f), "/dst/x.txt")


def test_upload_create_errno_raises(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "x.txt"
    f.write_bytes(b"x")
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U4", "block_list": []}
    api.xpanfilecreate.return_value = {"errno": -8}

    with pytest.raises(UploadError, match="errno=-8"):
        uploader.upload(str(f), "/dst/x.txt")


def test_upload_http_error_wrapped(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "x.txt"
    f.write_bytes(b"x")
    api.xpanfileprecreate.side_effect = ApiException(status=401, reason="Unauthorized")

    with pytest.raises(UploadError, match="401"):
        uploader.upload(str(f), "/dst/x.txt")


def test_upload_missing_local_file_raises():
    uploader, _ = _make_uploader()
    with pytest.raises(UploadError, match="本地文件不存在"):
        uploader.upload("/nonexistent/file.bin", "/dst/f.bin")


def test_upload_overwrite_rtype_forwarded(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "x.txt"
    f.write_bytes(b"x")
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U5", "block_list": []}
    api.xpanfilecreate.return_value = {"errno": 0}

    uploader.upload(str(f), "/dst/x.txt", rtype=3)
    assert api.xpanfileprecreate.call_args[1]["rtype"] == 3
    assert api.xpanfilecreate.call_args[1]["rtype"] == 3


def test_upload_progress_events(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "x.txt"
    f.write_bytes(b"xy")
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U6", "block_list": [0]}
    api.pcssuperfile2.return_value = {"md5": "x"}
    api.xpanfilecreate.return_value = {"errno": 0}

    events = []
    uploader.upload(str(f), "/dst/x.txt", progress=events.append)
    phases = [e["phase"] for e in events]
    assert phases == ["precreate", "chunk", "create"]
    assert events[1] == {"phase": "chunk", "seq": 0, "total": 1}


# ---------------------------------------------------------------------------
# 断点续传（本地状态文件）
# ---------------------------------------------------------------------------

STATE = {"local": "/src/f.bin", "remote": "/dst/f.bin"}


def _write_state(state_file, tmp_path, uploadid, md5s, uploaded, size=11, local=None, remote=None):
    import json as _json
    local = local or STATE["local"]
    remote = remote or STATE["remote"]
    key = f"{local}->{remote}"
    book = {
        key: {
            "local_path": local,
            "remote_path": remote,
            "size": size,
            "uploadid": uploadid,
            "md5s": md5s,
            "uploaded": uploaded,
        }
    }
    state_file.write_text(_json.dumps(book), encoding="utf-8")


def test_upload_resume_reuses_uploadid_and_skips_uploaded_chunks(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "f.bin"
    payload = os.urandom(CHUNK_SIZE * 2)
    f.write_bytes(payload)
    md5s = Uploader._hash_file(str(f), Uploader._plan_chunks(len(payload)))

    state_file = tmp_path / "state.json"
    _write_state(state_file, tmp_path, "U9", md5s, uploaded=[0], size=len(payload))
    api.pcssuperfile2.return_value = {"md5": "x"}
    api.xpanfilecreate.return_value = {"errno": 0, "path": "/dst/f.bin"}

    res = uploader.upload(
        str(f), "/dst/f.bin", state_file=state_file,
        local_key=STATE["local"],
    )
    assert res["errno"] == 0
    api.xpanfileprecreate.assert_not_called()  # 续传不重走预上传
    seqs = [c[1]["partseq"] for c in api.pcssuperfile2.call_args_list]
    assert seqs == ["1"]  # 仅补传缺失分片
    create_args = api.xpanfilecreate.call_args[1]
    assert create_args["uploadid"] == "U9"
    # 成功后状态清理
    assert not state_file.exists()


def test_upload_resume_complete_goes_straight_to_create(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "f.bin"
    payload = os.urandom(CHUNK_SIZE)
    f.write_bytes(payload)
    md5s = Uploader._hash_file(str(f), Uploader._plan_chunks(len(payload)))

    state_file = tmp_path / "state.json"
    _write_state(state_file, tmp_path, "U10", md5s, uploaded=[0], size=len(payload))
    api.xpanfilecreate.return_value = {"errno": 0}

    uploader.upload(str(f), "/dst/f.bin", state_file=state_file, local_key=STATE["local"])
    api.pcssuperfile2.assert_not_called()
    api.xpanfileprecreate.assert_not_called()
    api.xpanfilecreate.assert_called_once()


def test_upload_stale_state_falls_back_to_fresh(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "f.bin"
    payload = os.urandom(CHUNK_SIZE * 2)
    f.write_bytes(payload)

    state_file = tmp_path / "state.json"
    # 状态里的 md5s 与当前文件不符（文件已变更）→ 视为失效
    _write_state(state_file, tmp_path, "U11", ["deadbeef" * 4], uploaded=[0], size=len(payload))
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U12", "block_list": [0, 1]}
    api.pcssuperfile2.return_value = {"md5": "x"}
    api.xpanfilecreate.return_value = {"errno": 0}

    uploader.upload(str(f), "/dst/f.bin", state_file=state_file, local_key=STATE["local"])
    api.xpanfileprecreate.assert_called_once()  # 走全新预上传
    seqs = [c[1]["partseq"] for c in api.pcssuperfile2.call_args_list]
    assert seqs == ["0", "1"]
    # 全新流程使用新 uploadid
    assert api.xpanfilecreate.call_args[1]["uploadid"] == "U12"


def test_upload_fresh_flow_persists_state_after_precreate(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "f.bin"
    f.write_bytes(b"state test")

    state_file = tmp_path / "state.json"
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U13", "block_list": [0]}
    api.pcssuperfile2.return_value = {"md5": "x"}
    api.xpanfilecreate.return_value = {"errno": 0}

    uploader.upload(str(f), "/dst/f.bin", state_file=state_file, local_key=str(f))
    # 成功后状态文件被清理
    assert not state_file.exists()


def test_upload_state_persisted_mid_flow(tmp_path):
    uploader, api = _make_uploader()
    payload = os.urandom(CHUNK_SIZE * 2)
    f = tmp_path / "f.bin"
    f.write_bytes(payload)

    state_file = tmp_path / "state.json"
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U14", "block_list": [0, 1]}

    def chunk_then_fail_on_second(**kwargs):
        # 第一片成功，第二片服务端持续失败
        if kwargs["partseq"] == "0":
            return {"md5": "x"}
        raise UploadError("模拟服务端失败")

    api.pcssuperfile2.side_effect = chunk_then_fail_on_second

    with pytest.raises(UploadError):
        uploader.upload(str(f), "/dst/f.bin", state_file=state_file, local_key=str(f))

    # 中断后状态保留：uploadid + 已成功分片（键控账本格式）
    import json as _json
    book = _json.loads(state_file.read_text(encoding="utf-8"))
    record = book[f"{str(f)}->/dst/f.bin"]
    assert record["uploadid"] == "U14"
    assert record["uploaded"] == [0]
    assert record["remote_path"] == "/dst/f.bin"


def test_upload_resume_failure_falls_back_to_fresh(tmp_path):
    uploader, api = _make_uploader()
    f = tmp_path / "f.bin"
    payload = os.urandom(CHUNK_SIZE * 2)
    f.write_bytes(payload)
    md5s = Uploader._hash_file(str(f), Uploader._plan_chunks(len(payload)))

    state_file = tmp_path / "state.json"
    _write_state(state_file, tmp_path, "U15", md5s, uploaded=[0], size=len(payload))
    # 续传补片持续失败（uploadid 失效场景，片内 3 次重试均拒绝），回退全新流程后成功
    api.pcssuperfile2.side_effect = [
        UploadError("uploadid expired"),
        UploadError("uploadid expired"),
        UploadError("uploadid expired"),
        {"md5": "x"},
        {"md5": "x"},
    ]
    api.xpanfileprecreate.return_value = {"errno": 0, "uploadid": "U16", "block_list": [0, 1]}
    api.xpanfilecreate.return_value = {"errno": 0}

    uploader.upload(str(f), "/dst/f.bin", state_file=state_file, local_key=STATE["local"])
    assert api.xpanfilecreate.call_args[1]["uploadid"] == "U16"
    assert not state_file.exists()
