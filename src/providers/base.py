"""
API Monitor - Provider 抽象基类与辅助函数
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests

from ..models import ProviderResult, AccountConfig, StatusLevel

logger = logging.getLogger("api-monitor")


def format_balance(amount: float, symbol: str = "¥") -> str:
    """
    金额格式化
    - < 10000: ¥123.45
    - < 100000: ¥1.2K（保留1位小数）
    - >= 100000: ¥12W（取整）
    """
    if amount < 10_000:
        return f"{symbol}{amount:,.2f}"
    elif amount < 100_000:
        return f"{symbol}{amount / 1000:.1f}K"
    else:
        return f"{symbol}{amount / 10_000:.0f}W"


def format_tokens(count: float) -> str:
    """
    Token 数格式化
    - < 1M: 直接显示数字
    - >= 1M: 500M, 3.1B
    """
    if count < 1_000_000:
        return f"{count:,.0f}"
    elif count < 1_000_000_000:
        return f"{count / 1_000_000:.0f}M"
    else:
        return f"{count / 1_000_000_000:.1f}B"


class BaseProvider(ABC):
    """API 供应商抽象基类"""

    # 类属性：Provider 元信息（子类覆盖）
    PROVIDER_TYPE: str = ""           # 类型标识，如 "deepseek"
    PROVIDER_LABEL: str = ""          # 显示名称，如 "DeepSeek"
    API_BASE: str = ""                # API 基础 URL
    AUTH_TYPE: str = "bearer"         # 认证方式: "bearer" | "cookie"
    TIMEOUT: tuple = (5, 10)         # 请求超时 (连接s, 读取s)

    def __init__(self, account: AccountConfig):
        self.account = account
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """懒初始化 requests.Session"""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "APIMonitor/2.0",
            })
            self._set_auth(self._session)
        return self._session

    def _set_auth(self, session: requests.Session) -> None:
        """设置认证头（子类可覆盖）"""
        session.headers.update({
            "Authorization": f"Bearer {self.account.api_key}",
            "Accept": "application/json",
        })

    @abstractmethod
    def fetch(self) -> ProviderResult:
        """查询余额/用量，返回统一结果"""
        ...

    def test_connection(self) -> tuple[bool, str]:
        """测试连接是否正常，返回 (成功?, 消息)"""
        result = self.fetch()
        if result.status != StatusLevel.ERROR:
            return (True, "连接成功")
        return (False, result.error_message)

    def _handle_error(self, error: Exception) -> ProviderResult:
        """统一错误处理"""
        msg = "查询失败"
        if isinstance(error, requests.exceptions.Timeout):
            msg = "请求超时"
        elif isinstance(error, requests.exceptions.ConnectionError):
            msg = "网络连接失败"
        elif isinstance(error, requests.exceptions.HTTPError):
            code = error.response.status_code if error.response else 0
            if code == 401:
                msg = "API Key 无效或已过期"
            elif code == 429:
                msg = "请求过于频繁"
            else:
                msg = f"HTTP {code}"
        else:
            msg = str(error) or "未知错误"

        logger.error(f"[{self.PROVIDER_TYPE}] {self.account.name}: {msg}")

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=StatusLevel.ERROR,
            display_value="--",
            display_unit="",
            remaining_percent=None,
            error_message=msg,
        )

    def _status_from_percent(self, pct: float) -> StatusLevel:
        """剩余百分比转状态（≤5=ERROR, ≤20=WARNING, else NORMAL）"""
        if pct <= 5:
            return StatusLevel.ERROR
        elif pct <= 20:
            return StatusLevel.WARNING
        return StatusLevel.NORMAL

    def _status_from_used_percent(self, pct: float) -> StatusLevel:
        """已用百分比转状态（≥95=ERROR, ≥80=WARNING, else NORMAL）"""
        if pct >= 95:
            return StatusLevel.ERROR
        elif pct >= 80:
            return StatusLevel.WARNING
        return StatusLevel.NORMAL

    def _empty_result(self, msg: str = "无数据") -> ProviderResult:
        """返回空数据结果"""
        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=StatusLevel.WARNING,
            display_value="--",
            display_unit="",
            remaining_percent=None,
            detail=msg,
        )
