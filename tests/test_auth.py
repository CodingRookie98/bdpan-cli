"""Unit tests for TokenManager and multi-account support (BK-0035)."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from bdpan_cli.auth import TokenManager
from bdpan_cli.config import AppConfig


def _make_config():
    return AppConfig(app_key="dummy_key", secret_key="dummy_secret")


def test_legacy_cache_migration(tmp_path):
    cache_file = tmp_path / "tokens.json"
    legacy_data = {
        "access_token": "old_token",
        "refresh_token": "old_refresh",
        "expires_at": int(time.time()) + 3600 * 24 * 10,
    }
    cache_file.write_text(json.dumps(legacy_data))

    tm = TokenManager(_make_config(), cache_path=cache_file)
    # 应无缝读取旧 token
    assert tm.get_access_token() == "old_token"
    assert tm.get_active_account() == "default"

    # 验证文件已自动升级为多账号格式
    new_data = json.loads(cache_file.read_text())
    assert new_data["current"] == "default"
    assert "default" in new_data["accounts"]
    assert new_data["accounts"]["default"]["access_token"] == "old_token"


def test_multi_account_switch_and_list(tmp_path):
    cache_file = tmp_path / "tokens.json"
    data = {
        "current": "default",
        "accounts": {
            "default": {
                "access_token": "token_default",
                "refresh_token": "ref_default",
                "expires_at": int(time.time()) + 3600 * 48,
            },
            "backup": {
                "access_token": "token_backup",
                "refresh_token": "ref_backup",
                "expires_at": int(time.time()) + 3600 * 48,
            },
        },
    }
    cache_file.write_text(json.dumps(data))

    # 默认活跃账号
    tm = TokenManager(_make_config(), cache_path=cache_file)
    assert tm.get_active_account() == "default"
    assert tm.get_access_token() == "token_default"

    # 指定 account 参数
    tm_backup = TokenManager(_make_config(), account="backup", cache_path=cache_file)
    assert tm_backup.get_active_account() == "backup"
    assert tm_backup.get_access_token() == "token_backup"

    # 切换当前账号
    tm.switch_account("backup")
    assert tm.get_active_account() == "backup"
    assert tm.get_access_token() == "token_backup"

    # 列出账号列表
    accs = tm.list_accounts()
    assert len(accs) == 2
    acc_map = {a["account"]: a for a in accs}
    assert acc_map["backup"]["is_current"] is True
    assert acc_map["default"]["is_current"] is False


def test_switch_nonexistent_account_raises(tmp_path):
    cache_file = tmp_path / "tokens.json"
    data = {"current": "default", "accounts": {"default": {"access_token": "a", "expires_at": 9999999999}}}
    cache_file.write_text(json.dumps(data))

    tm = TokenManager(_make_config(), cache_path=cache_file)
    with pytest.raises(ValueError) as exc_info:
        tm.switch_account("non_existent")
    assert "不存在" in str(exc_info.value)


def test_token_manager_default_path_and_env_override(tmp_path, monkeypatch):
    custom_path = tmp_path / "custom" / "tokens.json"
    monkeypatch.setenv("BDPAN_TOKEN_PATH", str(custom_path))
    tm = TokenManager(_make_config())
    assert tm._cache_path == custom_path


def test_token_manager_auto_migrate_legacy_file(tmp_path, monkeypatch):
    target_cache = tmp_path / "xdg" / "tokens.json"
    legacy_file = tmp_path / "legacy" / ".baidupan_tokens.json"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_data = {
        "access_token": "legacy_tok",
        "refresh_token": "legacy_ref",
        "expires_at": int(time.time()) + 3600 * 24 * 10,
    }
    legacy_file.write_text(json.dumps(legacy_data))

    monkeypatch.setattr("bdpan_cli.auth.DEFAULT_TOKEN_FILE", target_cache)
    monkeypatch.setattr("bdpan_cli.auth.LEGACY_TOKEN_CACHE", legacy_file)
    monkeypatch.delenv("BDPAN_TOKEN_PATH", raising=False)

    tm = TokenManager(_make_config())
    assert tm.get_access_token() == "legacy_tok"
    assert target_cache.exists()
    migrated_json = json.loads(target_cache.read_text())
    assert migrated_json["current"] == "default"
    assert migrated_json["accounts"]["default"]["access_token"] == "legacy_tok"


def test_device_flow_triggers_browser_open(capsys):
    """验证设备码授权流程尝试自动打开浏览器并打印醒目授权码。"""
    tm = TokenManager(_make_config())

    mock_device = MagicMock()
    mock_device.verification_url = "https://pan.baidu.com/device"
    mock_device.user_code = "ABCD-1234"
    mock_device.device_code = "mock_device_code"
    mock_device.interval = 1
    mock_device.expires_in = 10

    mock_resp = MagicMock()
    mock_resp.access_token = "new_flow_token"
    mock_resp.refresh_token = "new_flow_refresh"
    mock_resp.expires_in = 3600

    with patch("bdpan_cli.auth.openapi_client.ApiClient") as mock_client_cls, \
         patch("bdpan_cli.auth.AuthApi") as mock_auth_cls, \
         patch("webbrowser.open") as mock_browser_open:

        mock_auth = MagicMock()
        mock_auth.oauth_token_device_code.return_value = mock_device
        mock_auth.oauth_token_device_token.return_value = mock_resp
        mock_auth_cls.return_value = mock_auth

        token = tm._device_flow()
        assert token["access_token"] == "new_flow_token"

        # 验证调用了 webbrowser.open 自动唤起浏览器
        mock_browser_open.assert_called_once_with("https://pan.baidu.com/device")

        # 验证终端输出了醒目的授权地址与用户码
        captured = capsys.readouterr()
        assert "https://pan.baidu.com/device" in captured.out
        assert "ABCD-1234" in captured.out



