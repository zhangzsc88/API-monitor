"""
API Monitor - DeepSeek 余额查询 Provider
"""
import logging

from .base import BaseProvider, format_balance
from ..models import ProviderResult, StatusLevel

logger = logging.getLogger("api-monitor")


class DeepSeekProvider(BaseProvider):
    """DeepSeek API 余额查询"""

    PROVIDER_TYPE = "deepseek"
    PROVIDER_LABEL = "DeepSeek"
    API_BASE = "https://api.deepseek.com"
    AUTH_TYPE = "bearer"

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/user/balance",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[DeepSeek] 响应: {data}")
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        balance_infos = data.get("balance_infos", [])
        if not balance_infos:
            return self._empty_result("无余额数据")

        info = balance_infos[0]  # 取第一个币种
        currency = info.get("currency", "CNY")
        total = float(info.get("total_balance", 0))
        granted = float(info.get("granted_balance", 0))
        topped = float(info.get("topped_up_balance", 0))
        symbol = "¥" if currency == "CNY" else "$"

        # 状态判断：余额为0则ERROR，低于阈值则WARNING
        threshold = self.account.warning_threshold
        status = StatusLevel.NORMAL
        if total <= 0:
            status = StatusLevel.ERROR
        elif threshold is not None and total < threshold:
            status = StatusLevel.WARNING

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=format_balance(total),
            display_unit="",
            remaining_percent=None,  # DeepSeek 无百分比
            detail=f"总额: {symbol}{total:,.2f}\n"
                   f"赠送: {symbol}{granted:,.2f}\n"
                   f"充值: {symbol}{topped:,.2f}",
            raw_data=data,
        )
