"""
API Monitor - MiniMax Token Plan 余额查询 Provider

MiniMax Token Plan 返回数据说明：
- model_remains 列表，每个元素是单个模型/池子的剩余状态
- general 池：current_interval_remaining_percent / current_weekly_remaining_percent
- 显示策略：主显示 = min(5h 池剩余, 周池剩余)，与 MiMo "剩余%" 语义一致
- 图标颜色 = 基于 remaining_percent 判断（同 MiMo 逻辑）
"""
import logging

from .base import BaseProvider
from ..models import ProviderResult, ModelQuota, StatusLevel

logger = logging.getLogger("api-monitor")


class MiniMaxTokenProvider(BaseProvider):
    """MiniMax Token Plan 余额查询"""

    PROVIDER_TYPE = "minimax_token"
    PROVIDER_LABEL = "MiniMax"
    API_BASE = "https://www.minimaxi.com"
    AUTH_TYPE = "bearer"

    def fetch(self) -> ProviderResult:
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/v1/token_plan/remains",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[MiniMaxToken] 响应: {data}")
            return self._parse(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse(self, data: dict) -> ProviderResult:
        base = data.get("base_resp", {})
        if base.get("status_code") != 0:
            return ProviderResult(
                provider_type=self.PROVIDER_TYPE,
                account_name=self.account.name,
                status=StatusLevel.ERROR,
                display_value="--",
                display_unit="",
                remaining_percent=None,
                error_message=base.get("status_msg", "查询失败"),
                raw_data=data,
            )

        models = data.get("model_remains", [])
        if not models:
            return self._empty_result("无配额数据")

        # 取 5h 池和周池的剩余百分比，取最小值
        primary = models[0]
        interval_remaining = primary.get("current_interval_remaining_percent")
        weekly_remaining = primary.get("current_weekly_remaining_percent")

        # 计算最小剩余百分比（最易触顶的维度）
        if interval_remaining is not None and weekly_remaining is not None:
            min_remaining = min(interval_remaining, weekly_remaining)
        elif interval_remaining is not None:
            min_remaining = interval_remaining
        elif weekly_remaining is not None:
            min_remaining = weekly_remaining
        else:
            min_remaining = None

        # 构建模型配额列表
        quotas = []
        for m in models:
            quotas.append(ModelQuota(
                name=m.get("model_name", "unknown"),
                remaining_percent=m.get("current_interval_remaining_percent"),
                used=m.get("current_interval_usage_count"),
                total=m.get("current_interval_total_count"),
                unit="%",
            ))

        # 状态判断：基于剩余百分比（与 MiMo 一致）
        if min_remaining is not None:
            status = self._status_from_percent(min_remaining)
            display_value = f"{min_remaining:.0f}"
            display_unit = "%"
        else:
            status = StatusLevel.WARNING
            display_value = "--"
            display_unit = ""

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=display_value,
            display_unit=display_unit,
            remaining_percent=min_remaining,
            detail=self._build_detail(quotas, interval_remaining, weekly_remaining),
            models=quotas,
            raw_data=data,
        )

    def _build_detail(self, quotas: list, interval_remaining, weekly_remaining) -> str:
        """构建详情文本（剩余语义，与 MiMo 一致）"""
        lines = []
        if interval_remaining is not None:
            used_pct = max(0, 100 - interval_remaining)
            lines.append(f"5h 池: 剩余 {interval_remaining:.0f}% (已用 {used_pct:.0f}%)")
        else:
            lines.append("5h 池: --")
        if weekly_remaining is not None:
            used_pct = max(0, 100 - weekly_remaining)
            lines.append(f"周池: 剩余 {weekly_remaining:.0f}% (已用 {used_pct:.0f}%)")
        else:
            lines.append("周池: --")
        if len(quotas) > 1:
            parts = []
            for q in quotas:
                if q.remaining_percent is not None:
                    parts.append(f"{q.name}: 剩余{q.remaining_percent:.0f}%")
                else:
                    parts.append(f"{q.name}: --")
            lines.append("  ".join(parts))
        return "\n".join(lines)
