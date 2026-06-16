"""
API Monitor - DeepSeek 余额 & 用量查询 Provider

两种模式：
1. API Key 模式（默认）：用 sk-xxx 查余额，简单稳定
2. 平台 Token 模式：用 localStorage 的 userToken 查余额+用量详情
   - 认证字段：extra.platform_token
   - 可查今日按模型的 token 用量（命中/未命中/输出）
   - 悬浮窗展示详细信息

平台 Token 获取方式：
1. 浏览器打开 https://platform.deepseek.com 并登录
2. F12 → Console → 输入: JSON.parse(localStorage.getItem('userToken')).value
3. 复制返回的 Token 字符串
"""
import logging
from datetime import date

from .base import BaseProvider, format_balance, format_tokens
from ..models import ProviderResult, StatusLevel

logger = logging.getLogger("api-monitor")


class DeepSeekProvider(BaseProvider):
    """DeepSeek API 余额 & 用量查询"""

    PROVIDER_TYPE = "deepseek"
    PROVIDER_LABEL = "DeepSeek"
    API_BASE = "https://api.deepseek.com"
    AUTH_TYPE = "bearer"

    # 平台内部接口
    PLATFORM_BASE = "https://platform.deepseek.com/api/v0"

    def fetch(self) -> ProviderResult:
        """根据认证方式自动选择查询模式"""
        platform_token = self.account.extra.get("platform_token", "").strip()
        if platform_token:
            return self._fetch_with_platform_token(platform_token)
        return self._fetch_with_api_key()

    # ── API Key 模式（余额查询）─────────────────────────────────────

    def _fetch_with_api_key(self) -> ProviderResult:
        """用 API Key 查余额（原有逻辑）"""
        try:
            resp = self._get_session().get(
                f"{self.API_BASE}/user/balance",
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[DeepSeek] 余额响应: {data}")
            return self._parse_balance(data)
        except Exception as e:
            return self._handle_error(e)

    def _parse_balance(self, data: dict) -> ProviderResult:
        balance_infos = data.get("balance_infos", [])
        if not balance_infos:
            return self._empty_result("无余额数据")

        info = balance_infos[0]
        currency = info.get("currency", "CNY")
        total = float(info.get("total_balance", 0))
        granted = float(info.get("granted_balance", 0))
        topped = float(info.get("topped_up_balance", 0))
        symbol = "¥" if currency == "CNY" else "$"

        status = StatusLevel.NORMAL
        if total <= 0:
            status = StatusLevel.ERROR

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=format_balance(total),
            display_unit="",
            remaining_percent=None,
            detail=f"总额: {symbol}{total:,.2f}\n"
                   f"赠送: {symbol}{granted:,.2f}\n"
                   f"充值: {symbol}{topped:,.2f}",
            raw_data=data,
        )

    # ── 平台 Token 模式（余额 + 用量详情）────────────────────────────

    def _fetch_with_platform_token(self, token: str) -> ProviderResult:
        """用平台 Token 查余额 + 今日用量详情"""
        import requests

        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "x-app-version": "1.0.0",
            "Origin": "https://platform.deepseek.com",
            "Referer": "https://platform.deepseek.com/usage",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })

        try:
            # 1. 查余额
            summary = self._platform_get(session, "/users/get_user_summary")

            # 2. 查今日用量
            today = date.today()
            usage = self._platform_get(session, "/usage/amount",
                                       month=today.month, year=today.year)

            # 3. 查今日费用
            cost = self._platform_get(session, "/usage/cost",
                                       month=today.month, year=today.year)

            session.close()
            return self._parse_platform_data(summary, usage, cost)

        except Exception as e:
            session.close()
            return self._handle_error(e)

    def _platform_get(self, session, path: str, **params):
        """请求平台内部接口，返回 biz_data 或 None"""
        try:
            resp = session.get(
                f"{self.PLATFORM_BASE}{path}",
                params=params,
                timeout=(10, 20),
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") != 0:
                logger.warning(f"[DeepSeek-Platform] 接口 {path} 返回 code={body.get('code')}")
                return None
            biz = body.get("data", {})
            if biz.get("biz_code") != 0:
                logger.warning(f"[DeepSeek-Platform] 接口 {path} 返回 biz_code={biz.get('biz_code')}")
                return None
            return biz.get("biz_data")
        except Exception as e:
            logger.warning(f"[DeepSeek-Platform] 接口 {path} 请求失败: {e}")
            return None

    def _parse_platform_data(self, summary, usage, cost) -> ProviderResult:
        """合并解析余额+用量+费用数据"""
        # ── 余额 ──
        total_balance = 0.0
        bonus_balance = 0.0
        monthly_tokens = 0
        monthly_cost = 0.0
        summary_ok = False

        if summary:
            summary_ok = True
            wallets = summary.get("normal_wallets", [])
            if wallets:
                total_balance = float(wallets[0].get("balance", "0"))
            bonus = summary.get("bonus_wallets", [])
            if bonus:
                bonus_balance = float(bonus[0].get("balance", "0"))
            monthly_tokens = int(summary.get("monthly_token_usage", "0"))
            costs_list = summary.get("monthly_costs", [])
            if costs_list:
                monthly_cost = float(costs_list[0].get("amount", "0"))

        # ── 今日用量（按模型） ──
        today = date.today().isoformat()
        today_prompt = 0
        today_completion = 0
        today_cache_hit = 0
        today_cache_miss = 0
        today_cost = 0.0
        model_details = []  # [(model_name, prompt, completion, cache_hit, cache_miss, cost)]

        if usage:
            days = usage.get("days", [])
            today_entry = next((d for d in days if d.get("date") == today), None)
            if today_entry:
                for model_entry in today_entry.get("data", []):
                    model_name = model_entry.get("model") or model_entry.get("model_name", "unknown")
                    model_name = self._friendly_model_name(model_name)
                    m_prompt = 0
                    m_completion = 0
                    m_cache_hit = 0
                    m_cache_miss = 0
                    for ut in model_entry.get("usage", []):
                        t = ut.get("type", "")
                        amt = int(ut.get("amount", "0"))
                        if t == "PROMPT_TOKEN":
                            m_prompt += amt
                        elif t == "PROMPT_CACHE_HIT_TOKEN":
                            m_prompt += amt
                            m_cache_hit += amt
                        elif t == "PROMPT_CACHE_MISS_TOKEN":
                            m_prompt += amt
                            m_cache_miss += amt
                        elif t == "RESPONSE_TOKEN":
                            m_completion += amt
                    today_prompt += m_prompt
                    today_completion += m_completion
                    today_cache_hit += m_cache_hit
                    today_cache_miss += m_cache_miss
                    model_details.append((model_name, m_prompt, m_completion, m_cache_hit, m_cache_miss))

        # ── 今日费用（按模型） ──
        model_costs = {}  # {model_name: cost}
        if cost:
            cost_container = cost[0] if isinstance(cost, list) else cost
            days = cost_container.get("days", [])
            today_entry = next((d for d in days if d.get("date") == today), None)
            if today_entry:
                for model_entry in today_entry.get("data", []):
                    raw_name = model_entry.get("model") or model_entry.get("model_name", "unknown")
                    friendly = self._friendly_model_name(raw_name)
                    m_cost = 0.0
                    for c in model_entry.get("usage", []):
                        m_cost += float(c.get("amount", "0"))
                        today_cost += float(c.get("amount", "0"))
                    model_costs[friendly] = m_cost

        # ── 构建结果 ──
        if not summary_ok and not usage:
            return self._empty_result("无法获取数据（Token 可能已过期）")

        # 状态判断
        status = StatusLevel.NORMAL
        if total_balance <= 0 and bonus_balance <= 0:
            status = StatusLevel.ERROR
        elif total_balance < 10:
            status = StatusLevel.WARNING

        # 主显示值：余额
        display_value = format_balance(total_balance + bonus_balance)
        display_unit = ""

        # 详情：余额明细 + 今日用量 + 按模型统计
        detail_lines = []
        detail_lines.append(f"余额: ¥{total_balance:,.2f}  赠送: ¥{bonus_balance:,.2f}")
        if monthly_tokens > 0:
            detail_lines.append(f"本月: {monthly_tokens:,} tokens  ¥{monthly_cost:.2f}")
        if today_prompt > 0 or today_completion > 0:
            total_prompt_tokens = today_cache_hit + today_cache_miss
            hit_rate = (today_cache_hit / total_prompt_tokens * 100) if total_prompt_tokens > 0 else 0
            # 今日汇总
            detail_lines.append(f"今日: 金额:¥{today_cost:.4f}")
            detail_lines.append(
                f"输入:{today_prompt:,} "
                f"输出:{today_completion:,} "
                f"命中:{hit_rate:.0f}%"
            )
            if today_cache_hit > 0 or today_cache_miss > 0:
                detail_lines.append(
                    f"命中:{today_cache_hit:,} 未命中:{today_cache_miss:,}"
                )
            # 按模型详情（显示所有模型，包括今日用量为0的）
            for model_name, m_prompt, m_completion, m_hit, m_miss in model_details:
                m_total = m_prompt + m_completion
                m_cost = model_costs.get(model_name, 0.0)
                if m_total > 0:
                    hit_rate = (m_hit / m_prompt * 100) if m_prompt > 0 else 0
                    detail_lines.append(f"{model_name}: 金额:¥{m_cost:.4f}")
                    detail_lines.append(
                        f"输入:{m_prompt:,} "
                        f"输出:{m_completion:,} "
                        f"命中:{hit_rate:.0f}%"
                    )
                    if m_hit > 0 or m_miss > 0:
                        detail_lines.append(
                            f"命中:{m_hit:,} 未命中:{m_miss:,}"
                        )
                else:
                    detail_lines.append(f"{model_name}: 今日未使用")

        return ProviderResult(
            provider_type=self.PROVIDER_TYPE,
            account_name=self.account.name,
            status=status,
            display_value=display_value,
            display_unit=display_unit,
            remaining_percent=None,
            detail="\n".join(detail_lines),
            raw_data={"summary": summary, "usage": usage, "cost": cost},
        )

    # 模型名称友好映射
    MODEL_ALIASES = {
        "deepseek-v4-pro": "V4-Pro",
        "deepseek-v4-flash": "V4-Flash",
        "deepseek-chat & deepseek-reasoner": "Chat/Reasoner",
        "deepseek-chat": "Chat",
        "deepseek-reasoner": "Reasoner",
    }

    @classmethod
    def _friendly_model_name(cls, name: str) -> str:
        return cls.MODEL_ALIASES.get(name, name)
