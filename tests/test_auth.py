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


