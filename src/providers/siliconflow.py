"""
API Monitor - 硅基流动 SiliconFlow 余额查询 Provider

支持两种认证模式：

1. API Key 认证（默认）：
   - 端点: https://api.siliconflow.cn/v1/user/info
   - 返回: balance(赠送) / chargeBalance(充值) / totalBalance(总)
   - 注意: 代金券余额不在此接口中，需 Cookie 模式查询

2. Cookie 认证（推荐，可查代金券明细）：
   - 基础余额: https://api.siliconflow.cn/v1/user/info（用 Bearer + Cookie）
   - 代金券钱包: https://cloud.siliconflow.cn/walletd-server/api/v1/subject/wallets?pageSize=10000&stage=3
   - 需要 __SF_auth.session-token Cookie + x-subject-id 请求头
   - 代金券余额单位 10^-12 元，需除以 1e12

Cookie 获取方式：
1. 浏览器打开 https://cloud.siliconflow.cn 并登录
2. F12 → Network → 刷新 → 随便点一个请求 → 复制 Cookie 头整串
3. 只需 __SF_auth.session-token 这一个字段即可
"""
import logging

from .base import BaseProvider, format_balance
from ..models import ProviderResult, StatusLevel

logger = logging.getLogger("api-monitor")

# 代金券余额单位转换：API 返回的 balance 单位是 10^-12 元
VOUCHER_BALANCE_DIVISOR = 1e12


class SiliconFlowProvider(BaseProvider):
    """硅基流动 SiliconFlow API 余额查询"""

    PROVIDER_TYPE = "siliconflow"
    PROVIDER_LABEL = "硅基流动"
    API_BASE = "https://api.siliconflow.cn/v1"
    CLOUD_BASE = "https://cloud.siliconflow.cn"
    AUTH_TYPE = "bearer"  # 默认，Cookie 模式时动态判断

    # Cookie 分字段名（仅 Cookie 模式使用）
    COOKIE_FIELDS = [
        ("cookie", "完整Cookie"),
    ]

    def _is_cookie_mode(self) -> bool:
        """判断是否使用 Cookie 认证模式"""
        cookie = self.account.extra.get("cookie", "").strip()
        return bool(cookie)

    def _build_cookie_string(self) -> str:
        """构建 Cookie 字符串"""
        return self.account.extra.get("cookie", "").strip()

    def _set_auth(self, session) -> None:
        """根据认证模式设置请求头"""
        if self._is_cookie_mode():
            cookie = self._build_cookie_string()
            session.headers.update({
                "Cookie": cookie,
                "Accept": "application/json",
                "Referer": "https://cloud.siliconflow.cn/account/balance",
            })
        else:
            session.headers.update({
                "Authorization": f"Bearer {self.account.api_key}",
                "Accept": "application/json",
            })

    def fetch(self) -> ProviderResult:
        try:
            if self._is_cookie_mode():
                return self._fetch_with_cookie()
            else:
                return self._fetch_with_apikey()
        except Exception as e:
            return self._handle_error(e)

    def _fetch_with_apikey(self) -> ProviderResult:
        """API Key 模式：仅查询基础余额"""
        resp = self._get_session().get(
            f"{self.API_BASE}/user/info",
            timeout=self.TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.debug(f"[SiliconFlow-APIKey] 响应: {data}")
        return self._parse_apikey(data)

    def _fetch_with_cookie(self) -> ProviderResult:
        """Cookie 模式：查询基础余额 + 代金券钱包"""
        session = self._get_session()

        # 1. 用 API Key 查基础余额（Cookie 单独查会 403）
        balance_data = {}
        subject_id = ""
        try:
            # 用 API Key 认证查基础余额
            resp = session.get(
                f"{self.API_BASE}/user/info",
                timeout=self.TIMEOUT,
                headers={"Authorization": f"Bearer {self.account.api_key}"},
            )
            resp.raise_for_status()
            balance_data = resp.json()
            subject_id = balance_data.get("data", {}).get("id", "")
            logger.debug(f"[SiliconFlow-Cookie] 余额响应: {balance_data}")
        except Exception as e:
            logger.warning(f"[SiliconFlow-Cookie] 查询基础余额失败: {e}")

        # 2. 用 Cookie + x-subject-id 查代金券钱包
        voucher_total = 0.0
        voucher_details = []
        if subject_id:
            try:
                cookie = self._build_cookie_string()
                resp2 = session.get(
                    f"{self.CLOUD_BASE}/walletd-server/api/v1/subject/wallets",
                    params={"pageSize": 10000, "stage": 3},
                    timeout=self.TIMEOUT,
                    headers={
                        "Cookie": cookie,
                        "x-subject-id": subject_id,
                        "Referer": f"https://cloud.siliconflow.cn/{subject_id}/balance",
                    },
                )
                resp2.raise_for_status()
                wallet_data = resp2.json()
                logger.debug(f"[SiliconFlow-Cookie] 代金券响应: {wallet_data}")
                voucher_total, voucher_details = self._parse_wallets(wallet_data)
            except Exception as e:
                logger.warning(f"[SiliconFlow-Cookie] 查询代金券失败: {e}")

        # 合并数据
        return self._parse_cookie(balance_data, voucher_total, voucher_details)

    def _parse_wallets(self, data: dict) -> tuple[float, list[str]]:
        """解析代金券钱包数据

        返回 (代金券总额, 代金券明细列表)
        代金券余额单位是 10^-12 元，需除以 1e12
        """
        if data.get("code") != 20000:
            return 0.0, []

        wallets = []
        data_inner = data.get("data", {})
        if isinstance(data_inner, dict):
            wallets = data_inner.get("wallets", data_inner.get("items", []))
        elif isinstance(data_inner, list):
            wallets = data_inner

        if not isinstance(wallets, list):
            return 0.0, []

        total = 0.0
        details = []
        for wallet in wallets:
            raw_balance = wallet.get("balance", 0)
            if isinstance(raw_balance, (int, float)):
                amount = raw_balance / VOUCHER_BALANCE_DIVISOR
            else:
                continue

            # 解析名称
            name = self._parse_wallet_name(wallet.get("name", ""))

            if amount > 0:
                total += amount
                details.append(f"{name}: ¥{amount:,.2f}")
            elif raw_balance == 0:
                cap_raw = wallet.get("cap", 0)
                if isinstance(cap_raw, (int, float)) and cap_raw > 0:
                    cap_amount = cap_raw / VOUCHER_BALANCE_DIVISOR
                    details.append(f"{name}: 已用完(原¥{cap_amount:,.0f})")

        return total, details

    def _parse_wallet_name(self, name_json: str) -> str:
        """从 JSON 字符串中解析代金券名称"""
        if not name_json:
            return "代金券"
        try:
            import json
            obj = json.loads(name_json)
            return obj.get("zh-cn", obj.get("en-us", str(obj)))
        except (json.JSONDecodeError, AttributeError):
            return name_json

    def _parse_apikey(self, data: dict) -> ProviderResult:
        """解析 API Key 模式响应"""
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

        # 显示 totalBalance，若为负则显示 0（代金券需 Cookie 模式查询）
        display_balance = max(total_balance, 0)

        # 状态判断
        threshold = self.account.warning_threshold
        status = StatusLevel.NORMAL
        if total_balance <= 0:
            status = StatusLevel.ERROR
        elif threshold is not None and total_balance < threshold:
            status = StatusLevel.WARNING

        # 构建详情
        detail_parts = []
        if balance > 0:
            detail_parts.append(f"赠送余额: ¥{balance:,.2f}")
        if charge_balance > 0:
            detail_parts.append(f"充值余额: ¥{charge_balance:,.2f}")
        elif charge_balance < 0:
            detail_parts.append(f"已消费: ¥{abs(charge_balance):,.2f}")
        detail_parts.append(f"API余额: ¥{total_balance:,.2f}")
        detail_parts.append("💡 填Cookie可查代金券明细")

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=format_balance(display_balance) if display_balance > 0 else "¥0",
            display_unit="",
            remaining_percent=None,
            detail="\n".join(detail_parts),
            raw_data=data,
        )

    def _parse_cookie(self, balance_data: dict, voucher_total: float, voucher_details: list[str]) -> ProviderResult:
        """解析 Cookie 模式响应（合并基础余额 + 代金券）"""
        # 解析基础余额
        total_balance = 0.0
        base_balance = 0.0
        charge_balance = 0.0
        if balance_data.get("code") == 20000:
            user_data = balance_data.get("data", {})
            total_balance = float(user_data.get("totalBalance", 0))
            base_balance = float(user_data.get("balance", 0))
            charge_balance = float(user_data.get("chargeBalance", 0))

        # 实际可用 = max(API余额, 0) + 代金券
        cash_balance = max(total_balance, 0)
        display_balance = cash_balance + voucher_total

        # 状态判断
        threshold = self.account.warning_threshold
        status = StatusLevel.NORMAL
        if display_balance <= 0:
            status = StatusLevel.ERROR
        elif threshold is not None and display_balance < threshold:
            status = StatusLevel.WARNING

        # 构建详情
        detail_parts = [f"总余额: ¥{display_balance:,.2f}"]

        if cash_balance > 0:
            detail_parts.append(f"现金余额: ¥{cash_balance:,.2f}")
        else:
            detail_parts.append(f"现金余额: ¥0.00")

        if base_balance > 0:
            detail_parts.append(f"赠送余额: ¥{base_balance:,.2f}")
        if charge_balance != 0:
            if charge_balance > 0:
                detail_parts.append(f"充值余额: ¥{charge_balance:,.2f}")
            else:
                detail_parts.append(f"已消费: ¥{abs(charge_balance):,.2f}")

        if voucher_total > 0:
            detail_parts.append(f"代金券: ¥{voucher_total:,.2f}")
            for vd in voucher_details:
                detail_parts.append(f"  {vd}")
        else:
            detail_parts.append("代金券: 无")

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=format_balance(display_balance),
            display_unit="",
            remaining_percent=None,
            detail="\n".join(detail_parts),
            raw_data={"balance": balance_data, "voucher_total": voucher_total},
        )
