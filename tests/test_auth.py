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
