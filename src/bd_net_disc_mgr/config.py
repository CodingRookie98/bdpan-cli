"""应用配置：从 .env 读取百度网盘开放平台凭证。"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    app_key: str
    secret_key: str


def load_config() -> AppConfig:
    load_dotenv()
    values = {
        "BAIDU_APP_KEY": os.getenv("BAIDU_APP_KEY", "").strip(),
        "BAIDU_SECRET_KEY": os.getenv("BAIDU_SECRET_KEY", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            f"缺少配置项：{'、'.join(missing)}，请在 .env 中填写（参考 .env.example）"
        )
    return AppConfig(values["BAIDU_APP_KEY"], values["BAIDU_SECRET_KEY"])
