"""access_token 的获取与缓存（设备码模式）。

access_token 有效期 30 天，refresh_token 有效期 10 年。
缓存文件不提交到 git（见 .gitignore）。
"""

import json
import os
from pathlib import Path
import time
from typing import Any

from bdpan_cli._vendor import openapi_client
from bdpan_cli._vendor.openapi_client.api.auth_api import AuthApi
from bdpan_cli._vendor.openapi_client.rest import ApiException
from bdpan_cli.config import AppConfig

# 默认用户端 Token 凭据路径遵循 XDG 规范 (~/.config/bdpan/tokens.json)
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "bdpan"
DEFAULT_TOKEN_FILE = DEFAULT_CONFIG_DIR / "tokens.json"
LEGACY_TOKEN_CACHE = Path(__file__).resolve().parents[2] / ".baidupan_tokens.json"

# 向后兼容常量导出
TOKEN_CACHE = DEFAULT_TOKEN_FILE
SCOPE = "basic,netdisk"
REFRESH_BEFORE_EXPIRY = 24 * 3600  # 剩余不足一天时先刷新


class AuthorizationNeeded(Exception):
    """需要用户完成设备码授权。"""


class TokenManager:
    """网盘授权凭证管理器，支持多账号别名存储与动态切换。"""

    def __init__(
        self,
        config: AppConfig,
        account: str | None = None,
        cache_path: Path | None = None,
    ) -> None:
        self._config = config
        self._account = account
        if cache_path:
            self._cache_path = Path(cache_path)
        else:
            env_path = os.environ.get("BDPAN_TOKEN_PATH")
            self._cache_path = Path(env_path) if env_path else DEFAULT_TOKEN_FILE

    def _normalize_token_data(self, raw: dict[str, Any]) -> dict[str, Any]:
        """标准化 token 字典，平滑兼容旧单账号形态与多账号形态。"""
        if "access_token" in raw:
            return {
                "current": "default",
                "accounts": {
                    "default": {
                        "access_token": raw.get("access_token"),
                        "refresh_token": raw.get("refresh_token"),
                        "expires_at": raw.get("expires_at"),
                    }
                },
            }
        if "accounts" not in raw or not isinstance(raw["accounts"], dict):
            raw["accounts"] = {}
        if "current" not in raw:
            raw["current"] = "default"
        return raw

    def _load_all(self) -> dict[str, Any]:
        """读取并兼容迁移缓存数据，返回统一的多账号结构字典。"""
        # 若目标文件不存在，但存在旧项目级 .baidupan_tokens.json，则自动无缝迁移至 ~/.config/bdpan/tokens.json
        if not self._cache_path.exists():
            if self._cache_path == DEFAULT_TOKEN_FILE and LEGACY_TOKEN_CACHE.exists():
                try:
                    legacy_data = json.loads(LEGACY_TOKEN_CACHE.read_text(encoding="utf-8"))
                    migrated = self._normalize_token_data(legacy_data)
                    self._save_all(migrated)
                    return migrated
                except (OSError, json.JSONDecodeError):
                    pass
            return {"current": "default", "accounts": {}}
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {"current": "default", "accounts": {}}
            if "access_token" in raw:
                migrated = self._normalize_token_data(raw)
                self._save_all(migrated)
                return migrated
            return self._normalize_token_data(raw)
        except (OSError, json.JSONDecodeError):
            return {"current": "default", "accounts": {}}

    def _save_all(self, data: dict[str, Any]) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        try:
            self._cache_path.chmod(0o600)
        except OSError:
            pass

    def get_active_account(self) -> str:
        """返回当前生效的账号别名。"""
        if self._account:
            return self._account
        all_data = self._load_all()
        return all_data.get("current") or "default"

    def get_access_token(self) -> str:
        account = self.get_active_account()
        all_data = self._load_all()
        cached = all_data.get("accounts", {}).get(account)
        if cached and "expires_at" in cached and "access_token" in cached:
            if cached["expires_at"] - time.time() > REFRESH_BEFORE_EXPIRY:
                return cached["access_token"]
            refreshed = self._refresh(cached.get("refresh_token", ""))
            if refreshed:
                return refreshed["access_token"]
        return self._device_flow()["access_token"]

    def _load_cache(self) -> dict[str, Any] | None:
        all_data = self._load_all()
        account = self.get_active_account()
        return all_data.get("accounts", {}).get(account)

    def _save_cache(self, token: dict[str, Any]) -> dict[str, Any]:
        account = self.get_active_account()
        all_data = self._load_all()
        if "accounts" not in all_data or not isinstance(all_data["accounts"], dict):
            all_data["accounts"] = {}
        all_data["accounts"][account] = token
        all_data["current"] = account
        self._save_all(all_data)
        return token

    def list_accounts(self) -> list[dict[str, Any]]:
        """列出本地所有保存的网盘账号信息。"""
        all_data = self._load_all()
        curr = all_data.get("current") or "default"
        accounts = all_data.get("accounts") or {}
        res = []
        for name, acc in accounts.items():
            expires_at = acc.get("expires_at") or 0
            is_valid = expires_at > time.time()
            res.append({
                "account": name,
                "is_current": (name == curr),
                "expires_at": expires_at,
                "valid": is_valid,
            })
        return res

    def switch_account(self, account: str) -> None:
        """切换默认活跃账号。"""
        all_data = self._load_all()
        if account not in all_data.get("accounts", {}):
            raise ValueError(f"账号 [{account}] 不存在，请先使用设备码授权登录该账号")
        all_data["current"] = account
        self._save_all(all_data)

    def remove_account(self, account: str) -> None:
        """移除指定账号凭证。"""
        all_data = self._load_all()
        accounts = all_data.get("accounts", {})
        if account in accounts:
            del accounts[account]
            if all_data.get("current") == account:
                all_data["current"] = next(iter(accounts.keys())) if accounts else "default"
            self._save_all(all_data)

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
