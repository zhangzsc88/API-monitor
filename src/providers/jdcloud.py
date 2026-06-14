"""
API Monitor - 京东云 JoyBuilder Coding Plan 用量查询 Provider
"""
import logging
from datetime import datetime

from .base import BaseProvider
from ..models import ProviderResult, StatusLevel

logger = logging.getLogger("api-monitor")


class JDCloudProvider(BaseProvider):
    """京东云 JoyBuilder Coding Plan 用量查询（Cookie 认证）"""

    PROVIDER_TYPE = "jdcloud"
    PROVIDER_LABEL = "京东云 JoyBuilder"
    API_BASE = "https://joybuilder-console.jdcloud.com/openApi"
    AUTH_TYPE = "cookie"

    # Cookie 分字段名
    COOKIE_FIELDS = [
        ("cookie_thor", "thor"),
        ("cookie_pin", "pin"),
    ]

    def _build_cookie_string(self) -> str:
        """从 extra 中的分字段拼接 Cookie 字符串"""
        parts = []
        for extra_key, cookie_key in self.COOKIE_FIELDS:
            val = self.account.extra.get(extra_key, "").strip()
            if val:
                parts.append(f"{cookie_key}={val}")
        if parts:
            return "; ".join(parts)
        # 兼容旧格式
        return self.account.extra.get("cookie", "") or self.account.api_key

    def _set_auth(self, session) -> None:
        """Cookie 认证"""
        cookie = self._build_cookie_string()
        session.headers.update({
            "Cookie": cookie,
            "Accept": "application/json",
            "Referer": "https://joybuilder-console.jdcloud.com/system/subscribe/list",
        })

    def fetch(self) -> ProviderResult:
        try:
            ts = int(datetime.now().timestamp() * 1000)
            resp = self._get_session().get(
                f"{self.API_BASE}/modelservice/describeUserActivePlan",
                params={"_t": ts},
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[JDCloud] 响应: {data}")
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        error = data.get("error")
        if error:
            return self._empty_result(f"API错误: {error}")

        result = data.get("result", {})
        if not result:
            return self._empty_result("无订阅数据")

        plan_name = result.get("name", "未知套餐")
        plan_type = result.get("plan_type", "")
        end_time = result.get("end_time", "")
        instance_id = result.get("instance_id", "")

        # 解析 limits 和 usages
        limits = {item["period"]: item["limit_value"] for item in result.get("limits", [])}
        usages = {item["type"]: item["count"] for item in result.get("usages", [])}

        # 计算剩余百分比（取最小的周期剩余）
        remaining_percents = []
        detail_lines = [f"套餐: {plan_name} ({plan_type})"]

        for period, limit in limits.items():
            used = usages.get(period, 0)
            remaining = limit - used
            pct = (remaining / limit * 100) if limit > 0 else 0
            remaining_percents.append(pct)

            # 周期显示名
            period_name = {"5hours": "5小时", "7days": "7天", "month": "月"}.get(period, period)
            detail_lines.append(f"{period_name}: {remaining:,}/{limit:,} 次 ({pct:.0f}% 剩余)")

        if end_time:
            detail_lines.append(f"到期: {end_time}")

        # 取最差（最小）的剩余百分比
        min_remaining = min(remaining_percents) if remaining_percents else 0

        # 状态判断
        status = StatusLevel.NORMAL
        if min_remaining <= 0:
            status = StatusLevel.ERROR
        elif min_remaining <= 20:
            status = StatusLevel.WARNING

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=f"{min_remaining:.0f}",
            display_unit="%",
            remaining_percent=min_remaining,
            detail="\n".join(detail_lines),
            raw_data=data,
        )
