"""access_token 的获取与缓存（设备码模式）。

access_token 有效期 30 天，refresh_token 有效期 10 年。
缓存文件不提交到 git（见 .gitignore）。
"""

import json
import time
from pathlib import Path

import openapi_client
from openapi_client.api.auth_api import AuthApi
from openapi_client.rest import ApiException

from bdpan_cli.config import AppConfig

TOKEN_CACHE = Path(__file__).resolve().parents[2] / ".baidupan_tokens.json"
SCOPE = "basic,netdisk"
REFRESH_BEFORE_EXPIRY = 24 * 3600  # 剩余不足一天时先刷新


class AuthorizationNeeded(Exception):
    """需要用户完成设备码授权。"""


class TokenManager:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def get_access_token(self) -> str:
        cached = self._load_cache()
        if cached:
            if cached["expires_at"] - time.time() > REFRESH_BEFORE_EXPIRY:
                return cached["access_token"]
            refreshed = self._refresh(cached.get("refresh_token", ""))
            if refreshed:
                return refreshed["access_token"]
        return self._device_flow()["access_token"]

    def _load_cache(self) -> dict | None:
        if not TOKEN_CACHE.exists():
            return None
        try:
            return json.loads(TOKEN_CACHE.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _save_cache(self, token: dict) -> dict:
        TOKEN_CACHE.write_text(json.dumps(token, indent=2))
        return token

    def _to_cache(self, response) -> dict:
        return {
            "access_token": response.access_token,
            "refresh_token": response.refresh_token,
            "expires_at": int(time.time()) + int(response.expires_in),
        }

    def _refresh(self, refresh_token: str) -> dict | None:
        if not refresh_token:
            return None
        try:
            with openapi_client.ApiClient() as client:
                response = AuthApi(client).oauth_token_refresh_token(
                    refresh_token, self._config.app_key, self._config.secret_key
                )
        except ApiException:
            return None
        return self._save_cache(self._to_cache(response))

    def _device_flow(self) -> dict:
        with openapi_client.ApiClient() as client:
            auth = AuthApi(client)
            device = auth.oauth_token_device_code(self._config.app_key, SCOPE)
            interval = max(int(device.interval or 5), 3)
            deadline = time.time() + int(device.expires_in or 300)
            print(
                f"请打开 {device.verification_url} ，输入用户码 {device.user_code} 并确认授权",
                flush=True,
            )
            while time.time() < deadline:
                time.sleep(interval)
                try:
                    response = auth.oauth_token_device_token(
                        device.device_code,
                        self._config.app_key,
                        self._config.secret_key,
                    )
                except ApiException as e:
                    body = getattr(e, "body", "") or ""
                    if "authorization_pending" in body:
                        continue
                    if "slow_down" in body:
                        interval += 5
                        continue
                    raise RuntimeError(f"设备码授权失败：{body}") from e
                print("授权成功", flush=True)
                return self._save_cache(self._to_cache(response))
        raise AuthorizationNeeded("设备码已过期，请重新运行")
