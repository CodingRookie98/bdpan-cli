"""应用配置：从环境变量、本地 .env 或 XDG 全局配置读取百度网盘开放平台凭证。"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# XDG 全局配置目录与文件 (~/.config/bdpan/.env)
DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bdpan"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / ".env"


class ConfigError(RuntimeError):
    """应用配置缺失或无效异常。"""


@dataclass(frozen=True)
class AppConfig:
    app_key: str
    secret_key: str


def get_global_config_path() -> Path:
    """获取全局 .env 配置文件的实际路径。"""
    custom = os.environ.get("BDPAN_CONFIG_PATH")
    if custom:
        return Path(custom)
    return DEFAULT_CONFIG_FILE


def load_config() -> AppConfig:
    """按优先级检索并加载百度开放平台凭证：
    1. 进程内既有环境变量 (os.environ)
    2. 当前工作目录下的 .env 文件
    3. 全局 XDG 配置文件 (~/.config/bdpan/.env)

    若全部未配置，抛出友好的 ConfigError。
    """
    # 1. 尝试从当前目录加载 .env (override=False 保护已存在的环境变量)
    local_env = Path.cwd() / ".env"
    if local_env.is_file():
        load_dotenv(dotenv_path=local_env, override=False)

    # 2. 尝试从全局 XDG 配置加载 .env (override=False 保护优先由本地 .env 或环境变量指定的值)
    global_env = get_global_config_path()
    if global_env.is_file():
        load_dotenv(dotenv_path=global_env, override=False)

    values = {
        "BAIDU_APP_KEY": os.getenv("BAIDU_APP_KEY", "").strip(),
        "BAIDU_SECRET_KEY": os.getenv("BAIDU_SECRET_KEY", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigError(
            f"缺少必要配置项：{'、'.join(missing)}。\n"
            "请通过以下任一方式配置：\n"
            "  1. 快速配置（推荐）：bdpan auth config --app-key <KEY> --secret-key <SECRET>\n"
            f"  2. 全局配置文件：在 {global_env} 中填写\n"
            "  3. 当前目录：在当前工作目录下 .env 中填写\n"
            "  4. 环境变量：export BAIDU_APP_KEY=... BAIDU_SECRET_KEY=..."
        )
    return AppConfig(values["BAIDU_APP_KEY"], values["BAIDU_SECRET_KEY"])


def save_global_config(app_key: str, secret_key: str, path: Path | None = None) -> Path:
    """将 AppKey 和 SecretKey 保存至全局 .env 配置文件（强制权限 0o600）。"""
    target_path = path or get_global_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# 百度网盘开放平台开发者凭证 (XDG 全局配置)\n"
        f"BAIDU_APP_KEY={app_key.strip()}\n"
        f"BAIDU_SECRET_KEY={secret_key.strip()}\n"
    )
    target_path.write_text(content, encoding="utf-8")
    try:
        target_path.chmod(0o600)
    except OSError:
        pass
    return target_path
