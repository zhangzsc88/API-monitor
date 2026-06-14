"""
API Monitor - 小米 MiMo Token Plan 用量查询 Provider

注意：小米 MiMo 的用量查询只能通过 Cookie 认证，
API Key（tp-xxxxx）仅用于调用模型 API，不支持用量查询。

Cookie 获取方式：
1. 浏览器打开 https://platform.xiaomimimo.com 并登录
2. F12 打开 DevTools → Application → Cookies
3. 复制所有 Cookie 内容

Cookie 有效期约 24 小时，过期需重新获取。
"""
import logging

from .base import BaseProvider, format_tokens
from ..models import ProviderResult, ModelQuota, StatusLevel

logger = logging.getLogger("api-monitor")


class MiMoProvider(BaseProvider):
    """小米 MiMo Token Plan 用量查询（Cookie 认证）"""

    PROVIDER_TYPE = "mimo"
    PROVIDER_LABEL = "小米 MiMo"
    API_BASE = "https://platform.xiaomimimo.com"
    AUTH_TYPE = "cookie"

    # Token 格式化缩放因子（与 cc-switch 一致）
    SCALE = 1_000_000  # 除以 1M 得到 "百M" 单位

    # Cookie 分字段名（前端填写、存储在 extra 中的 key）
    COOKIE_FIELDS = [
        ("cookie_userId", "userId"),
        ("cookie_serviceToken", "serviceToken"),
        ("cookie_api_platform_serviceToken", "api-platform_serviceToken"),
    ]

    def _build_cookie_string(self) -> str:
        """从 extra 中的分字段拼接 Cookie 字符串

        优先使用分字段格式（cookie_userId / cookie_serviceToken / ...），
        若不存在则回退到旧格式 extra.cookie（完整 Cookie 字符串）。
        """
        parts = []
        for extra_key, cookie_key in self.COOKIE_FIELDS:
            val = self.account.extra.get(extra_key, "").strip()
            if val:
                parts.append(f"{cookie_key}={val}")

        if parts:
            return "; ".join(parts)

        # 兼容旧格式：整串 Cookie
        return self.account.extra.get("cookie", "") or self.account.api_key

    def _set_auth(self, session) -> None:
        """Cookie 认证：从分字段拼接或从旧格式读取"""
        cookie = self._build_cookie_string()
        session.headers.update({
            "Cookie": cookie,
            "Accept": "application/json",
            "Referer": "https://platform.xiaomimimo.com/console/plan-manage",
            "X-Timezone": "Asia/Shanghai",
        })

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/api/v1/tokenPlan/usage",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            # 检查业务状态码
            if data.get("code") != 0:
                msg = data.get("message", "未知错误")
                if data.get("code") == 401:
                    msg = "Cookie 已过期，请重新获取"
                logger.warning(f"[MiMo] {self.account.name}: 业务错误 code={data.get('code')}, msg={msg}")
                return ProviderResult(
                    provider_type=self.PROVIDER_TYPE,
                    account_name=self.account.name,
                    status=StatusLevel.ERROR,
                    display_value="--",
                    display_unit="",
                    remaining_percent=None,
                    error_message=msg,
                    raw_data=data,
                )

            logger.debug(f"[MiMo] 响应: {data}")
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        """解析 MiMo TokenPlan 用量响应

        响应格式（来自 cc-switch 实测）：
        {
          "code": 0,
          "data": {
            "monthUsage": {
              "percent": 0.5,
              "items": [{"name": "monthly_total_token", "used": N, "limit": N, "percent": 0.5}]
            },
            "usage": {
              "percent": 0.3,
              "items": [
                {"name": "plan_total_token", "used": N, "limit": N, "percent": 0.3},
                {"name": "compensation_total_token", "used": N, "limit": N, "percent": 0.5}
              ]
            }
          }
        }
        """
        data_inner = data.get("data", {})

        # 解析套餐用量（Token Plan）
        usage = data_inner.get("usage", {})
        plan_items = usage.get("items", [])

        # 解析月度用量
        month_usage = data_inner.get("monthUsage", {})
        month_items = month_usage.get("items", [])

        quotas = []
        min_pct = 100.0

        # 套餐积分
        plan_item = self._find_item(plan_items, "plan_total_token")
        if plan_item:
            q = self._build_quota("套餐积分", plan_item)
            quotas.append(q)
            min_pct = min(min_pct, q.remaining_percent or 0)

        # 补偿积分
        comp_item = self._find_item(plan_items, "compensation_total_token")
        if comp_item:
            q = self._build_quota("补偿积分", comp_item)
            quotas.append(q)
            min_pct = min(min_pct, q.remaining_percent or 0)

        # 月度用量
        month_item = self._find_item(month_items, "monthly_total_token")
        if month_item:
            q = self._build_quota("月度用量", month_item)
            quotas.append(q)
            min_pct = min(min_pct, q.remaining_percent or 0)

        if not quotas:
            return self._empty_result("无配额数据")

        status = self._status_from_percent(min_pct)
        primary = quotas[0]  # 以套餐积分为主要显示

        # 显示值：使用最低剩余百分比（与其他 Provider 一致）
        # 图标文字空间有限，百分比比 token 数更直观

        detail_lines = []
        for q in quotas:
            remaining_val = (q.total or 0) - (q.used or 0)
            detail_lines.append(
                f"{q.name}: {q.remaining_percent:.0f}% "
                f"({format_tokens(remaining_val)}/{format_tokens(q.total or 0)})"
            )

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=f"{min_pct:.0f}",
            display_unit="%",
            remaining_percent=min_pct,
            detail="\n".join(detail_lines),
            models=quotas,
            raw_data=data,
        )

    def _find_item(self, items: list, name: str) -> dict | None:
        """从 items 列表中查找指定名称的项"""
        for item in items:
            if item.get("name") == name:
                return item
        return None

    def _build_quota(self, label: str, item: dict) -> ModelQuota:
        """从 API item 构建 ModelQuota

        item 格式: {"name": "plan_total_token", "used": N, "limit": N, "percent": 0.3}
        percent 是已用百分比（0-1），需转换为剩余百分比（0-100）
        """
        used = item.get("used", 0)
        limit = item.get("limit", 0)
        pct_used = item.get("percent", 0)  # 已用百分比 0-1

        # 剩余百分比 = (1 - 已用%) * 100
        remaining_pct = (1 - pct_used) * 100

        return ModelQuota(
            name=label,
            remaining_percent=remaining_pct,
            used=used,
            total=limit,
            unit="tokens",
        )

    def _format_display(self, remaining_tokens: float) -> str:
        """格式化显示值：除以 SCALE 得到 '百M' 单位"""
        if remaining_tokens <= 0:
            return "0"
        val = remaining_tokens / self.SCALE
        if val >= 10_000:
            return f"{val / 10_000:.1f}B"
        elif val >= 100:
            return f"{val:.0f}M"
        else:
            return f"{val:.1f}M"
