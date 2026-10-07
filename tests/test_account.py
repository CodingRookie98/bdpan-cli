"""Unit tests for AccountClient (容量与用户信息查询)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openapi_client.rest import ApiException

from bdpan_cli.account import AccountClient, AccountError


class _FakeModel:
    """模拟 UserinfoApi 返回的 SDK 模型对象（带 attribute_map 而非裸 dict）。"""

    attribute_map = {"errno": "errno", "total": "total", "used": "used"}

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _make_client() -> tuple[AccountClient, MagicMock]:
    mock_client = MagicMock()
    client = AccountClient("fake-token", mock_client)
    client._userinfo_api = MagicMock()
    return client, client._userinfo_api


def test_quota_success_dict_passthrough():
    client, api = _make_client()
    api.apiquota.return_value = {"errno": 0, "total": 3221225472000, "used": 1073741824000}

    res = client.quota()
    assert res["total"] == 3221225472000
    assert res["used"] == 1073741824000
    api.apiquota.assert_called_once_with(
        access_token="fake-token", checkexpire=0, checkfree=0
    )


def test_quota_flags_forwarded():
    client, api = _make_client()
    api.apiquota.return_value = {"errno": 0, "total": 1, "used": 0, "expire": 1893456000}

    client.quota(check_expire=True, check_free=True)
    api.apiquota.assert_called_once_with(
        access_token="fake-token", checkexpire=1, checkfree=1
    )


def test_quota_model_object_normalized():
    client, api = _make_client()
    # UserinfoApi 返回 SDK 模型对象而非 dict，需归一化
    api.apiquota.return_value = _FakeModel(errno=0, total=100, used=40)

    res = client.quota()
    assert res == {"errno": 0, "total": 100, "used": 40}


def test_quota_server_errno_raises():
    client, api = _make_client()
    api.apiquota.return_value = {"errno": 111, "errmsg": "token expired"}

    with pytest.raises(AccountError, match="errno=111"):
        client.quota()


def test_quota_http_error_wrapped():
    client, api = _make_client()
    api.apiquota.side_effect = ApiException(status=401, reason="Unauthorized")

    with pytest.raises(AccountError, match="401"):
        client.quota()


def test_user_info_success():
    client, api = _make_client()
    fake = SimpleNamespace(
        errno=0, baidu_name="alice", netdisk_name="alice_net", vip_type=2
    )
    fake.attribute_map = {
        "errno": "errno",
        "baidu_name": "baidu_name",
        "netdisk_name": "netdisk_name",
        "vip_type": "vip_type",
    }
    api.xpannasuinfo.return_value = fake

    res = client.user_info()
    assert res["baidu_name"] == "alice"
    assert res["netdisk_name"] == "alice_net"
    assert res["vip_type"] == 2
    api.xpannasuinfo.assert_called_once_with(access_token="fake-token")


def test_unrecognized_response_type_raises():
    client, api = _make_client()
    api.apiquota.return_value = ["not", "a", "dict"]

    with pytest.raises(AccountError, match="无法解析的响应类型"):
        client.quota()
