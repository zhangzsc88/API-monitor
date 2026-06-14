"""
API Monitor - 硅基流动 SiliconFlow 余额查询 Provider
"""
import logging

from .base import BaseProvider, format_balance
from ..models import ProviderResult, StatusLevel

logger = logging.getLogger("api-monitor")


class SiliconFlowProvider(BaseProvider):
    """硅基流动 SiliconFlow API 余额查询"""

    PROVIDER_TYPE = "siliconflow"
    PROVIDER_LABEL = "硅基流动"
    API_BASE = "https://api.siliconflow.cn/v1"
    AUTH_TYPE = "bearer"

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/user/info",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[SiliconFlow] 响应: {data}")
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        # 硅基流动返回格式: {"code": 20000, "data": {"balance": "12.34", ...}}
        code = data.get("code")
        if code != 20000:
            msg = data.get("message", "未知错误")
            return self._empty_result(f"API错误: {msg}")

        user_data = data.get("data", {})
        if not user_data:
            return self._empty_result("无余额数据")

        balance = float(user_data.get("balance", 0))
        charge_balance = float(user_data.get("chargeBalance", 0))
        total_balance = float(user_data.get("totalBalance", 0))

        # 状态判断
        threshold = self.account.warning_threshold
        status = StatusLevel.NORMAL
        if total_balance <= 0:
            status = StatusLevel.ERROR
        elif threshold is not None and total_balance < threshold:
            status = StatusLevel.WARNING

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=format_balance(total_balance),
            display_unit="",
            remaining_percent=None,
            detail=f"总余额: ¥{total_balance:,.2f}\n"
                   f"可用余额: ¥{balance:,.2f}\n"
                   f"充值余额: ¥{charge_balance:,.2f}",
            raw_data=data,
        )
