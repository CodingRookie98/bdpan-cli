"""Unit tests for configuration loading, XDG global config, and auth config command (BK-0043)."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from bdpan_cli.cli import main
from bdpan_cli.config import (
    ConfigError,
    get_global_config_path,
    load_config,
    save_global_config,
)


def test_load_config_from_environ(monkeypatch):
    """验证直接从已设置的环境变量中读取凭据。"""
    monkeypatch.setenv("BAIDU_APP_KEY", "env_app_key")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "env_secret_key")

    cfg = load_config()
    assert cfg.app_key == "env_app_key"
    assert cfg.secret_key == "env_secret_key"


def test_load_config_from_global_xdg(tmp_path, monkeypatch):
    """验证当环境变量与本地 .env 缺失时，自动降级从 XDG 全局配置读取。"""
    monkeypatch.delenv("BAIDU_APP_KEY", raising=False)
    monkeypatch.delenv("BAIDU_SECRET_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    global_env = tmp_path / "global" / ".env"
    monkeypatch.setenv("BDPAN_CONFIG_PATH", str(global_env))

    # 此时全局文件不存在，应抛出 ConfigError
    with pytest.raises(ConfigError) as exc_info:
        load_config()
    assert "缺少必要配置项" in str(exc_info.value)
    assert "bdpan auth config" in str(exc_info.value)

    # 写入全局配置
    save_global_config("xdg_app_key", "xdg_secret_key", path=global_env)
    assert global_env.exists()

    cfg = load_config()
    assert cfg.app_key == "xdg_app_key"
    assert cfg.secret_key == "xdg_secret_key"


def test_save_global_config_permissions(tmp_path):
    """验证 save_global_config 创建文件并设置安全权限 (0o600)。"""
    target = tmp_path / "subdir" / ".env"
    saved = save_global_config("my_key", "my_secret", path=target)
    assert saved == target
    assert target.exists()

    content = target.read_text(encoding="utf-8")
    assert "BAIDU_APP_KEY=my_key" in content
    assert "BAIDU_SECRET_KEY=my_secret" in content

    # 验证权限 0o600 (仅用户可读写)
    mode = target.stat().st_mode & 0o777
    assert mode == 0o600


def test_cli_auth_config_path(capsys, monkeypatch, tmp_path):
    """验证 bdpan auth config --path 输出全局配置文件路径。"""
    custom_path = tmp_path / "custom" / ".env"
    monkeypatch.setenv("BDPAN_CONFIG_PATH", str(custom_path))

    exit_code = main(["auth", "config", "--path"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert str(custom_path) in captured.out


def test_cli_auth_config_write(capsys, monkeypatch, tmp_path):
    """验证 bdpan auth config --app-key ... --secret-key ... 成功写入配置。"""
    custom_path = tmp_path / "custom" / ".env"
    monkeypatch.setenv("BDPAN_CONFIG_PATH", str(custom_path))

    exit_code = main([
        "auth",
        "config",
        "--app-key",
        "cli_test_key",
        "--secret-key",
        "cli_test_secret",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "✅ 开发者凭证已成功保存至全局配置" in captured.out
    assert str(custom_path) in captured.out

    content = custom_path.read_text(encoding="utf-8")
    assert "BAIDU_APP_KEY=cli_test_key" in content
    assert "BAIDU_SECRET_KEY=cli_test_secret" in content


def test_cli_auth_config_show(capsys, monkeypatch, tmp_path):
    """验证 bdpan auth config --show 正确展示脱敏后的凭证信息。"""
    custom_path = tmp_path / "custom" / ".env"
    monkeypatch.setenv("BDPAN_CONFIG_PATH", str(custom_path))
    monkeypatch.setenv("BAIDU_APP_KEY", "ak_1234567890")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "sk_abcdefghij")

    exit_code = main(["auth", "config", "--show"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "📋 百度网盘开放平台开发者凭证配置状态" in captured.out
    assert "ak_...890" in captured.out
    assert "sk_...hij" in captured.out


def test_cli_auth_config_missing_args(capsys, monkeypatch):
    """验证非交互终端下未传参数时报错并给出明确使用示例。"""
    # 模拟非 tty 终端
    with patch("sys.stdin.isatty", return_value=False):
        exit_code = main(["auth", "config"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "缺少凭据参数" in captured.err
        assert "bdpan auth config --app-key" in captured.err


def test_cli_graceful_config_error_no_traceback(capsys, monkeypatch):
    """验证当缺少凭据时，运行任意命令均输出友好错误提示，无裸露 Python Traceback。"""
    monkeypatch.delenv("BAIDU_APP_KEY", raising=False)
    monkeypatch.delenv("BAIDU_SECRET_KEY", raising=False)

    with patch("bdpan_cli.config.load_dotenv"):
        exit_code = main(["ls", "/"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "❌ 配置缺失: 缺少必要配置项" in captured.err
        assert "Traceback" not in captured.err
        assert "bdpan auth config" in captured.err


def test_cli_graceful_config_error_json_mode(capsys, monkeypatch):
    """验证 --json 模式下配置缺失时返回标准失败信封。"""
    monkeypatch.delenv("BAIDU_APP_KEY", raising=False)
    monkeypatch.delenv("BAIDU_SECRET_KEY", raising=False)

    with patch("bdpan_cli.config.load_dotenv"):
        exit_code = main(["--json", "ls", "/"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert '"success": false' in captured.out
        assert "缺少必要配置项" in captured.out
