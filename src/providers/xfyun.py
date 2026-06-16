"""
API Monitor - 讯飞星辰 MaaS Astron Coding Plan 用量查询 Provider
"""
import logging

import requests

from .base import BaseProvider
from ..models import ProviderResult, StatusLevel

logger = logging.getLogger("api-monitor")


class XfyunProvider(BaseProvider):
    """讯飞星辰 MaaS Astron Coding Plan 用量查询（Cookie 认证）"""

    PROVIDER_TYPE = "xfyun"
    PROVIDER_LABEL = "讯飞星辰"
    API_BASE = "https://maas.xfyun.cn/api/v1/gpt-finetune"
    AUTH_TYPE = "cookie"

    # Cookie 分字段名 — 只需 ssoSessionId
    COOKIE_FIELDS = [
        ("cookie_ssoSessionId", "ssoSessionId"),
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
            "Referer": "https://maas.xfyun.cn/packageSubscription",
        })

    TIMEOUT = (10, 20)  # 讯飞 API 响应较慢，放宽超时

    def fetch(self) -> ProviderResult:
        try:
            # 每次新建 session 避免连接复用问题（讯飞 Cookie API 对连接复用敏感）
            session = requests.Session()
            session.headers.update({"User-Agent": "APIMonitor/2.0"})
            self._set_auth(session)
            resp = session.get(
                f"{self.API_BASE}/coding-plan/list",
                params={"page": 1, "size": 10},
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[Xfyun] 响应: {data}")
            session.close()
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        code = data.get("code")
        if code == 4001:
            return self._empty_result("Cookie 已过期，请重新获取 ssoSessionId")
        if code != 0:
            msg = data.get("message", f"API错误 code={code}")
            return self._empty_result(msg)

        rows = data.get("data", {}).get("rows", [])
        if not rows:
            return self._empty_result("无 Coding Plan 套餐")

        # 汇总所有套餐用量
        all_remaining_percents = []
        detail_lines = []

        for i, row in enumerate(rows):
            usage = row.get("codingPlanUsageDTO", {})
            app_id = row.get("appId", f"套餐{i+1}")
            expires = row.get("expiresAt", "")

            # 模型信息
            models = row.get("modelInfo", [])
            model_names = [m.get("name", "") for m in models if m.get("default")]
            active_model = model_names[0] if model_names else ""

            # 用量数据
            rp5h_usage = usage.get("rp5hUsage", 0) or 0
            rp5h_limit = usage.get("rp5hLimit", 0) or 0
            rpw_usage = usage.get("rpwUsage", 0) or 0
            rpw_limit = usage.get("rpwLimit", 0) or 0
            pkg_usage = usage.get("packageUsage", 0) or 0
            pkg_limit = usage.get("packageLimit", 0) or 0
            pkg_left = usage.get("packageLeft", 0) or 0

            # 无忧版（不限量）：rp5hLimit/rpwLimit/packageLimit 可能为 -1
            is_unlimited = (rp5h_limit < 0 and rpw_limit < 0 and pkg_limit < 0)

            if is_unlimited:
                detail_lines.append(f"[{app_id}] 无忧版（不限量）")
                if active_model:
                    detail_lines.append(f"  当前模型: {active_model}")
                detail_lines.append(f"  5小时: {rp5h_usage} 次")
                detail_lines.append(f"  本周: {rpw_usage} 次")
                detail_lines.append(f"  本月: {pkg_usage} 次")
                if expires:
                    detail_lines.append(f"  到期: {expires}")
                # 不限量时按 100% 算
                all_remaining_percents.append(100.0)
            else:
                # 计算各周期剩余百分比
                percents = []

                if rp5h_limit > 0:
                    rp5h_remaining = rp5h_limit - rp5h_usage
                    rp5h_pct = max(0, rp5h_remaining / rp5h_limit * 100)
                    percents.append(rp5h_pct)
                    detail_lines.append(f"  5小时: {rp5h_remaining:,}/{rp5h_limit:,} 次 ({rp5h_pct:.0f}%)")

                if rpw_limit > 0:
                    rpw_remaining = rpw_limit - rpw_usage
                    rpw_pct = max(0, rpw_remaining / rpw_limit * 100)
                    percents.append(rpw_pct)
                    detail_lines.append(f"  本周: {rpw_remaining:,}/{rpw_limit:,} 次 ({rpw_pct:.0f}%)")

                if pkg_limit > 0:
                    pkg_pct = max(0, pkg_left / pkg_limit * 100)
                    percents.append(pkg_pct)
                    detail_lines.append(f"  本月: {pkg_left:,}/{pkg_limit:,} 次 ({pkg_pct:.0f}%)")

                header = f"[{app_id}]"
                if active_model:
                    header += f" {active_model}"
                detail_lines.insert(-len(percents) if percents else 0, header)

                if expires:
                    detail_lines.append(f"  到期: {expires}")

                # 取最差周期剩余
                if percents:
                    all_remaining_percents.append(min(percents))

        # 取所有套餐中最差的一个
        min_remaining = min(all_remaining_percents) if all_remaining_percents else 0

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
