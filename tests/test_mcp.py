"""测试原生 MCP (Model Context Protocol) Server 协议与工具调用。"""

from unittest.mock import MagicMock
import json
import pytest

from bdpan_cli.mcp_server import BdpanMcpServer


def test_mcp_initialize():
    server = BdpanMcpServer(lambda: "fake_token")
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    resp = server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    result = resp["result"]
    assert result["serverInfo"]["name"] == "bdpan-mcp"
    assert result["protocolVersion"] == "2024-11-05"
    assert "tools" in result["capabilities"]


def test_mcp_ping():
    server = BdpanMcpServer(lambda: "fake_token")
    req = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
    resp = server.handle_request(req)
    assert resp["id"] == 2
    assert resp["result"] == {}


def test_mcp_tools_list():
    server = BdpanMcpServer(lambda: "fake_token")
    req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
    resp = server.handle_request(req)
    assert resp["id"] == 3
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]

    expected = [
        "bdpan_ls",
        "bdpan_mkdir",
        "bdpan_mv",
        "bdpan_cp",
        "bdpan_rm",
        "bdpan_rename",
        "bdpan_search",
        "bdpan_tree",
        "bdpan_quota",
        "bdpan_whoami",
        "bdpan_info",
        "bdpan_stats",
        "bdpan_ops_list",
        "bdpan_undo",
    ]
    for exp in expected:
        assert exp in tool_names
        # 确保每个工具都有有效的 inputSchema
        t = next(x for x in tools if x["name"] == exp)
        assert t["inputSchema"]["type"] == "object"
        assert len(t["description"]) > 0


def test_mcp_call_whoami():
    server = BdpanMcpServer(lambda: "fake_token")
    mock_client = MagicMock()
    mock_client.user_info.return_value = {
        "baidu_name": "developer_test",
        "netdisk_name": "网盘用户A",
        "vip_type": 2,
    }
    server._get_account_client = lambda: mock_client

    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "bdpan_whoami",
            "arguments": {},
        },
    }
    resp = server.handle_request(req)
    assert resp["id"] == 4
    res = resp["result"]
    assert res["isError"] is False
    content = res["content"][0]["text"]
    assert "developer_test" in content
    assert "超级会员" in content


def test_mcp_call_ls():
    server = BdpanMcpServer(lambda: "fake_token")
    mock_fm = MagicMock()
    mock_fm.list_dir.return_value = [
        {"server_filename": "movies", "isdir": 1, "size": 0, "path": "/movies"},
        {"server_filename": "demo.mp4", "isdir": 0, "size": 1048576, "path": "/demo.mp4"},
    ]
    server._get_file_manager = lambda: mock_fm

    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "bdpan_ls",
            "arguments": {"path": "/"},
        },
    }
    resp = server.handle_request(req)
    assert resp["id"] == 5
    res = resp["result"]
    assert res["isError"] is False
    content = res["content"][0]["text"]
    assert "movies" in content
    assert "demo.mp4" in content


def test_mcp_call_unknown_tool():
    server = BdpanMcpServer(lambda: "fake_token")
    req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "bdpan_non_existent",
            "arguments": {},
        },
    }
    resp = server.handle_request(req)
    assert resp["id"] == 6
    res = resp["result"]
    assert res["isError"] is True
    assert "未知的工具" in res["content"][0]["text"]


def test_mcp_unknown_method():
    server = BdpanMcpServer(lambda: "fake_token")
    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "non_standard_method",
        "params": {},
    }
    resp = server.handle_request(req)
    assert resp["id"] == 7
    assert "error" in resp
    assert resp["error"]["code"] == -32601
