"""
DeepSeek Monitor - API 调用模块
"""
import requests
import logging
from datetime import datetime, date

logger = logging.getLogger("deepseek-monitor")

BASE_URL = "https://api.deepseek.com"
TIMEOUT = 15  # 请求超时秒数


class DeepSeekAPI:
    """DeepSeek API 客户端"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })

    def get_balance(self):
        """
        查询账户余额
        返回: dict 或 None
        {
            "is_available": bool,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "123.45",
                    "granted_balance": "0.00",
                    "topped_up_balance": "123.45"
                }
            ]
        }
        """
        try:
            resp = self.session.get(
                f"{BASE_URL}/user/balance",
                timeout=TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.debug(f"Balance response: {data}")
                return data
            elif resp.status_code == 401:
                logger.error("API Key 无效或已过期")
                return None
            else:
                logger.error(f"查询余额失败: HTTP {resp.status_code} - {resp.text[:200]}")
                return None
        except requests.exceptions.Timeout:
            logger.error("查询余额超时")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("无法连接 DeepSeek API，请检查网络")
            return None
        except Exception as e:
            logger.error(f"查询余额异常: {e}")
            return None

    def test_connection(self):
        """测试 API Key 是否有效"""
        result = self.get_balance()
        return result is not None and result.get("is_available") is not None


def parse_balance(data, currency="CNY"):
    """
    从 API 响应中解析余额
    返回: dict
    {
        "currency": str,
        "total_balance": float,
        "granted_balance": float,
        "topped_up_balance": float,
        "is_available": bool,
    }
    """
    if not data:
        return None

    is_available = data.get("is_available", False)
    balance_infos = data.get("balance_infos", [])

    target = None
    for info in balance_infos:
        if info.get("currency") == currency:
            target = info
            break

    # 如果没找到目标货币，取第一个
    if not target and balance_infos:
        target = balance_infos[0]

    if not target:
        return None

    return {
        "currency": target.get("currency", currency),
        "total_balance": float(target.get("total_balance", "0")),
        "granted_balance": float(target.get("granted_balance", "0")),
        "topped_up_balance": float(target.get("topped_up_balance", "0")),
        "is_available": is_available,
    }


def estimate_tokens_consumed(balance_diff, price_per_m=4.0):
    """
    根据余额差额估算 Token 消耗
    balance_diff: 余额减少量（元）
    price_per_m: 每百万 token 价格（元）
    返回: 估算 token 数
    """
    if balance_diff <= 0:
        return 0
    return int(balance_diff / price_per_m * 1_000_000)
