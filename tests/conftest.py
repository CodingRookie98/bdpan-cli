"""全局测试配置与 Fixtures。"""

import pytest


@pytest.fixture(autouse=True)
def ensure_test_env(monkeypatch):
    """为单测注入基础凭证环境变量，防止在无 .env 的纯净 CI 容器中触发缺参异常。"""
    monkeypatch.setenv("BAIDU_APP_KEY", "mock_baidu_app_key")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "mock_baidu_secret_key")
