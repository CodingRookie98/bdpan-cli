"""账户信息客户端，封装网盘容量与用户信息查询。"""

from __future__ import annotations

from typing import Any

import openapi_client
from openapi_client.api.userinfo_api import UserinfoApi
from openapi_client.rest import ApiException


class AccountError(RuntimeError):
    """账户信息查询异常。"""


class AccountClient:
    """网盘账户信息封装（容量配额、用户资料）。"""

    def __init__(self, access_token: str, api_client: openapi_client.ApiClient | None = None) -> None:
        self.access_token = access_token
        self.api_client = api_client or openapi_client.ApiClient()
        self._userinfo_api = UserinfoApi(self.api_client)

    def quota(self, check_expire: bool = False, check_free: bool = False) -> dict[str, Any]:
        """查询网盘容量配额。

        Args:
            check_expire: 同时返回会员容量过期时间（expire 字段）。
            check_free: 同时返回免费容量配额（free 字段）。

        Returns:
            含 total / used（字节）等键的容量信息字典。
        """
        try:
            res = self._userinfo_api.apiquota(
                access_token=self.access_token,
                checkexpire=1 if check_expire else 0,
                checkfree=1 if check_free else 0,
            )
        except ApiException as e:
            raise AccountError(f"查询网盘容量失败: {e.status} {e.body}") from e
        return self._validate(self._normalize(res), "查询网盘容量")

    def user_info(self) -> dict[str, Any]:
        """查询网盘用户信息（百度账号、网盘名、会员类型）。

        Returns:
            含 baidu_name / netdisk_name / vip_type 等键的用户信息字典。
        """
        try:
            res = self._userinfo_api.xpannasuinfo(access_token=self.access_token)
        except ApiException as e:
            raise AccountError(f"查询用户信息失败: {e.status} {e.body}") from e
        return self._validate(self._normalize(res), "查询用户信息")

    @staticmethod
    def _normalize(res: Any) -> dict[str, Any]:
        """统一响应形态。

        UserinfoApi 经 SDK 反序列化返回模型对象而非裸 dict（区别于
        FileinfoApi 等直接返回 dict 的接口），需归一化：优先 to_dict()，
        退化按 attribute_map 逐键取值。
        """
        if isinstance(res, dict):
            return res
        to_dict = getattr(res, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        attr_map = getattr(res, "attribute_map", None)
        if isinstance(attr_map, dict):
            return {key: getattr(res, key, None) for key in attr_map}
        raise AccountError(f"无法解析的响应类型: {type(res).__name__}")

    @staticmethod
    def _validate(res: dict[str, Any], ctx: str) -> dict[str, Any]:
        if res.get("errno") not in (0, None):
            raise AccountError(f"{ctx}返回错误: errno={res.get('errno')} ({res})")
        return res
